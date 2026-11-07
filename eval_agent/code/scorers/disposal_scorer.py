import re
from typing import Any, Dict, List, Tuple

from ..judge_client import JudgeClient, JudgeError
from ..models import EvalTask, RunResult


RUBRIC_WEIGHTS = {
    "offense_and_disposition": 0.25,
    "rag_evidence_use": 0.25,
    "key_factors": 0.25,
    "recommendation_quality": 0.15,
    "uncertainty_and_consistency": 0.10,
}

RUBRIC_NAMES = {
    "offense_and_disposition": "罪名与处置方向",
    "rag_evidence_use": "类案证据使用",
    "key_factors": "关键处置因素",
    "recommendation_quality": "建议可用性",
    "uncertainty_and_consistency": "不确定性与结论一致性",
}

SYSTEM_PROMPT = """你是法律 Agent 处置建议评测器。你只按预先给定的固定 Rubric 逐项判断，不得自行增加检查项。

评分规则：
1. 罪名与处置方向：判断主要罪名、责任方向和处置类型是否合理；不要求复现真实案件的精确刑期或罚金。
2. 类案证据使用：若 RAG 返回了足够且可比的类案，检查回答是否使用真实 evidence、保留完整 sourceId、比较
   关键差异，并给出有依据的刑期/罚金参考区间；若证据不足或不可比，明确说明不足且未强行预测也可以通过。
3. 关键处置因素：检查人工标注的量刑/处置因素是否得到覆盖，不要求使用完全相同的措辞。
4. 建议可用性：检查是否给出可执行的处置方向、合理区间、补证重点或风险提示；只罗列材料而不形成建议应失败。
5. 不确定性与结论一致性：检查结论是否由案件事实和本轮 evidence 支持，是否区分参考区间与确定裁判结果。

实际历史刑期和罚金不会提供给你，也不属于主评分要求。不得因为回答没有命中某个精确月份或金额而判失败。
只有罪名或责任方向明显错误、结论与关键事实直接冲突、编造来源/关键事实，或者在证据明显不足时给出高风险
的确定性错误建议，才能标记 severe_error=true。

必须只输出 JSON，items 必须包含下面 5 个 id 且不得增加其他项：
{"items":[
 {"id":"offense_and_disposition","result":"pass|fail|na","reason":"说明"},
 {"id":"rag_evidence_use","result":"pass|fail|na","reason":"说明"},
 {"id":"key_factors","result":"pass|fail|na","reason":"说明"},
 {"id":"recommendation_quality","result":"pass|fail|na","reason":"说明"},
 {"id":"uncertainty_and_consistency","result":"pass|fail|na","reason":"说明"}
],"severe_error":布尔值,"severe_error_reason":""}。"""


def score_disposal(task: EvalTask, run: RunResult, judge: JudgeClient) -> Dict[str, Any]:
    if run.status != "completed":
        return {"status": "not_scored", "reason": "agent_run_failed"}
    if not judge.enabled:
        return {"status": "not_scored", "reason": "judge_not_configured"}
    case_facts = ""
    if task.active_case:
        case_facts = str(task.active_case.get("structuredFacts", {}).get("caseFacts", ""))
    reference_rubric, observed_outcome = _split_reference(
        task.reference.get("disposal_points", [])
    )
    try:
        judged = judge.evaluate(
            SYSTEM_PROMPT,
            {
                "case_facts": case_facts,
                "reference_rubric": reference_rubric,
                "rag_evidence": run.rag_evidence,
                "agent_answer": run.answer,
            },
        )
    except JudgeError as exc:
        return {"status": "not_scored", "reason": "judge_failed", "detail": str(exc)}

    items = _fixed_items(judged.get("items"))
    applicable = [item for item in items if item["result"] in {"pass", "fail"}]
    applicable_weight = sum(float(item["weight"]) for item in applicable)
    passed_weight = sum(
        float(item["weight"]) for item in applicable if item["result"] == "pass"
    )
    severe_error = bool(judged.get("severe_error"))
    score = round(passed_weight / applicable_weight, 6) if applicable_weight else 0.0
    return {
        "status": "scored",
        "score": score,
        "passed_items": sum(item["result"] == "pass" for item in applicable),
        "applicable_items": len(applicable),
        "severe_error": severe_error,
        "passed": not severe_error and score >= 0.75,
        "reference_rubric": reference_rubric,
        # Kept for offline comparison only. It is deliberately not sent to Judge.
        "observed_outcome": observed_outcome,
        "details": {
            "items": items,
            "severe_error": severe_error,
            "severe_error_reason": str(judged.get("severe_error_reason", "")),
        },
    }


def _split_reference(points: Any) -> Tuple[Dict[str, Any], Dict[str, str]]:
    rubric: Dict[str, Any] = {
        "offense_direction": "",
        "disposition_type": "",
        "required_factors": [],
    }
    observed: Dict[str, str] = {}
    if not isinstance(points, list):
        return rubric, observed
    for raw in points:
        point = str(raw).strip()
        label, separator, value = point.partition("：")
        if not separator:
            continue
        value = value.strip()
        if label == "罪名":
            rubric["offense_direction"] = value
        elif label == "处置方式":
            rubric["disposition_type"] = value
        elif label == "量刑考虑":
            rubric["required_factors"] = [
                item.strip() for item in re.split(r"[、，,]", value) if item.strip()
            ]
        elif label == "刑期结果":
            observed["sentence"] = value
        elif label == "罚金结果":
            observed["fine"] = value
    return rubric, observed


def _fixed_items(value: Any) -> List[Dict[str, Any]]:
    supplied: Dict[str, Dict[str, Any]] = {}
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("id", ""))
            if item_id not in RUBRIC_WEIGHTS or item_id in supplied:
                continue
            status = str(item.get("result", "")).lower()
            if status not in {"pass", "fail", "na"}:
                continue
            supplied[item_id] = item

    result: List[Dict[str, Any]] = []
    for item_id, weight in RUBRIC_WEIGHTS.items():
        item = supplied.get(item_id)
        result.append(
            {
                "id": item_id,
                "name": RUBRIC_NAMES[item_id],
                "weight": weight,
                "result": str(item.get("result")) if item else "fail",
                "reason": str(item.get("reason", ""))
                if item
                else "Judge 未返回该固定检查项",
            }
        )
    return result
