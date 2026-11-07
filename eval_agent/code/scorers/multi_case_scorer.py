import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from ..judge_client import JudgeClient
from ..models import EvalTask, RunResult


FIELD_ALIASES = {
    "person": "person",
    "persons": "person",
    "time": "time",
    "times": "time",
    "location": "location",
    "locations": "location",
    "behavior": "behavior",
    "behaviors": "behavior",
    "number": "numbers",
    "numbers": "numbers",
    "responsibility": "responsibility",
    "responsibilities": "responsibility",
    "consequence": "consequence",
    "consequences": "consequence",
}


def score_multi_case(
    task: EvalTask, run: RunResult, _judge: JudgeClient
) -> Dict[str, Any]:
    """Score structured multi-case extraction without an LLM judge."""
    if run.status != "completed":
        return {"status": "not_scored", "reason": "agent_run_failed"}

    parsed, parse_error = _parse_answer(run.answer)
    if parse_error:
        return _invalid_output_score(task, parse_error)

    expected_scope = _string_list(task.reference.get("expected_scope"))
    fact_map = task.reference.get("case_fact_map", {})
    all_case_ids = list(fact_map) if isinstance(fact_map, dict) else []
    expected = _flatten_expected(fact_map, expected_scope)
    all_expected = _flatten_expected(fact_map, all_case_ids)
    actual, actual_case_ids = _flatten_actual(parsed)

    matched_expected: Set[int] = set()
    matched_actual: Set[int] = set()
    correct: List[Dict[str, str]] = []
    for actual_index, actual_fact in enumerate(actual):
        match_index = _find_match(actual_fact, expected, matched_expected, same_case=True)
        if match_index is None:
            continue
        matched_expected.add(match_index)
        matched_actual.add(actual_index)
        correct.append(_comparison(actual_fact, expected[match_index]))

    misattributed: List[Dict[str, str]] = []
    misattributed_actual: Set[int] = set()
    for actual_index, actual_fact in enumerate(actual):
        if actual_index in matched_actual:
            continue
        match_index = _find_match(actual_fact, all_expected, set(), same_case=False)
        if match_index is None:
            continue
        expected_fact = all_expected[match_index]
        if expected_fact["case_id"] == actual_fact["case_id"]:
            continue
        misattributed_actual.add(actual_index)
        misattributed.append(_comparison(actual_fact, expected_fact))

    missing = [fact for index, fact in enumerate(expected) if index not in matched_expected]
    extra = [fact for index, fact in enumerate(actual) if index not in matched_actual]
    target_set = set(expected_scope)
    non_target_actual: Set[int] = {
        index for index, fact in enumerate(actual) if fact["case_id"] not in target_set
    }
    forbidden_facts = [
        fact
        for fact in all_expected
        if fact["case_id"] not in target_set
        and not any(_same_value(fact, target) for target in expected)
    ]
    for actual_index, actual_fact in enumerate(actual):
        if actual_index in non_target_actual:
            continue
        if any(_same_value(actual_fact, fact) for fact in forbidden_facts):
            non_target_actual.add(actual_index)

    true_positive = len(correct)
    expected_count = len(expected)
    output_count = len(actual)
    precision = _ratio(true_positive, output_count)
    recall = _ratio(true_positive, expected_count)
    f1 = _f1(precision, recall)
    confusion_rate = _ratio(len(misattributed_actual), output_count)
    leakage_rate = _ratio(len(non_target_actual), output_count)
    missing_case_ids = sorted(target_set - actual_case_ids)
    unexpected_case_ids = sorted(actual_case_ids - target_set)
    targeted = len(expected_scope) < len(all_case_ids)
    passed = (
        f1 >= 0.8
        and not misattributed
        and not missing_case_ids
        and not unexpected_case_ids
        and (not targeted or not non_target_actual)
    )

    return {
        "status": "scored",
        "passed": passed,
        "score": f1,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_rate": confusion_rate,
        "non_target_leakage_rate": leakage_rate,
        "true_positive": true_positive,
        "expected_fact_count": expected_count,
        "output_fact_count": output_count,
        "misattributed_fact_count": len(misattributed_actual),
        "non_target_fact_count": len(non_target_actual),
        "missing_case_ids": missing_case_ids,
        "unexpected_case_ids": unexpected_case_ids,
        "correct_facts": correct,
        "missing_facts": missing,
        "extra_facts": extra,
        "misattributed_facts": misattributed,
        "category": task.metadata.get("category"),
    }


def _invalid_output_score(task: EvalTask, detail: str) -> Dict[str, Any]:
    return {
        "status": "scored",
        "passed": False,
        "score": 0.0,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "confusion_rate": 0.0,
        "non_target_leakage_rate": 0.0,
        "true_positive": 0,
        "expected_fact_count": _expected_count(task),
        "output_fact_count": 0,
        "misattributed_fact_count": 0,
        "non_target_fact_count": 0,
        "reason": "invalid_structured_output",
        "detail": detail,
        "category": task.metadata.get("category"),
    }


def _parse_answer(answer: str) -> Tuple[Dict[str, Any], Optional[str]]:
    text = answer.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        start = text.find("{")
        if start >= 0:
            text = text[start:]
    try:
        value, _ = json.JSONDecoder().raw_decode(text)
    except (json.JSONDecodeError, ValueError) as exc:
        return {}, f"Agent 未返回合法 JSON：{exc}"
    if not isinstance(value, dict) or not isinstance(value.get("cases"), list):
        return {}, "Agent JSON 必须包含 cases 数组"
    return value, None


def _flatten_expected(fact_map: Any, scope: List[str]) -> List[Dict[str, str]]:
    if not isinstance(fact_map, dict):
        return []
    result: List[Dict[str, str]] = []
    for case_id in scope:
        case = fact_map.get(case_id)
        facts = case.get("facts") if isinstance(case, dict) else None
        result.extend(flatten_fact_fields(case_id, facts))
    return result


def _flatten_actual(parsed: Dict[str, Any]) -> Tuple[List[Dict[str, str]], Set[str]]:
    result: List[Dict[str, str]] = []
    case_ids: Set[str] = set()
    for case in parsed.get("cases", []):
        if not isinstance(case, dict):
            continue
        case_id = case.get("caseId")
        if not isinstance(case_id, str) or not case_id.strip():
            continue
        case_id = case_id.strip()
        case_ids.add(case_id)
        result.extend(flatten_fact_fields(case_id, case.get("facts")))
    return result, case_ids


def flatten_fact_fields(case_id: str, facts: Any) -> List[Dict[str, str]]:
    if not isinstance(facts, dict):
        return []
    result: List[Dict[str, str]] = []
    for raw_field, raw_values in facts.items():
        field = FIELD_ALIASES.get(str(raw_field))
        if field is None:
            continue
        values = raw_values if isinstance(raw_values, list) else [raw_values]
        for value in values:
            if isinstance(value, (str, int, float)) and str(value).strip():
                result.append({"case_id": case_id, "field": field, "value": str(value).strip()})
    return result


def _find_match(
    actual: Dict[str, str],
    expected: List[Dict[str, str]],
    used: Set[int],
    *,
    same_case: bool,
) -> Optional[int]:
    for index, candidate in enumerate(expected):
        if index in used or actual["field"] != candidate["field"]:
            continue
        if same_case and actual["case_id"] != candidate["case_id"]:
            continue
        if facts_equivalent(actual["value"], candidate["value"], actual["field"]):
            return index
    return None


def _same_value(left: Dict[str, str], right: Dict[str, str]) -> bool:
    return left["field"] == right["field"] and facts_equivalent(
        left["value"], right["value"], left["field"]
    )


def facts_equivalent(left: str, right: str, field: str = "") -> bool:
    if field == "numbers":
        left_numbers = re.findall(r"\d+(?:\.\d+)?", left)
        right_numbers = re.findall(r"\d+(?:\.\d+)?", right)
        if left_numbers and right_numbers:
            return set(left_numbers).issubset(right_numbers) or set(right_numbers).issubset(
                left_numbers
            )
    if field == "time":
        left_numbers = re.findall(r"\d+", left)
        right_numbers = re.findall(r"\d+", right)
        if left_numbers and right_numbers:
            return set(left_numbers).issubset(right_numbers) or set(right_numbers).issubset(
                left_numbers
            )
    left_norm = _normalize(left, field)
    right_norm = _normalize(right, field)
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm or left_norm in right_norm or right_norm in left_norm:
        return True
    if field == "behavior":
        concepts = [
            ("驾驶", "酒后"),
            ("盗窃",),
            ("贩卖", "毒品"),
            ("故意伤害",),
            ("滥用职权", "收受财物"),
            ("开设赌场",),
            ("强奸",),
            ("暴力", "劫取"),
            ("要挟", "索取"),
            ("赌博",),
            ("票据", "骗取"),
            ("徇私", "降格"),
            ("藏匿",),
            ("国家工作人员", "谋取利益"),
            ("行贿",),
            ("销售", "器材"),
        ]
        return any(
            all(token in left_norm for token in concept)
            and all(token in right_norm for token in concept)
            for concept in concepts
        )
    if field == "consequence":
        outcome_tokens = (
            "车辆受损",
            "人员受伤",
            "轻伤二级",
            "财物被盗",
            "交易",
            "查获",
            "经济损失",
            "收受贿赂",
            "赌场",
            "中止",
            "劫取",
            "索取财物",
            "赌资",
            "销赃",
            "降格",
            "藏匿",
            "谋取",
            "补偿",
            "扣押",
        )
        return any(token in left_norm and token in right_norm for token in outcome_tokens)
    return False


def _normalize(value: str, field: str = "") -> str:
    text = re.sub(r"[\s，,。；;：:（）()【】\[\]‘’'\"=／/]", "", value).lower()
    if field == "behavior":
        replacements = {
            "醉酒驾驶": "酒后驾驶",
            "醉酒后": "酒后",
            "窃取": "盗窃",
            "毒品贩卖": "贩卖毒品",
            "海洛因": "毒品",
            "砍伤": "伤害",
            "索要": "索取",
            "给予国家工作人员财物以谋取利益": "行贿",
            "实施": "",
            "等相关行为": "",
        }
        for source, target in replacements.items():
            text = text.replace(source, target)
    elif field == "responsibility":
        text = text.replace("承担事故", "事故").replace("负本次事故", "事故")
    elif field == "location":
        text = re.sub(r"^(?:本市|[^市]{2,8}市)", "", text)
    elif field == "consequence":
        replacements = {
            "损坏": "受损",
            "致人受伤": "人员受伤",
            "造成伤害": "人员受伤",
            "成交": "交易",
            "抓获": "查获",
            "窃取": "盗窃",
            "盗窃他人财物": "财物被盗",
        }
        for source, target in replacements.items():
            text = text.replace(source, target)
    return text


def _comparison(actual: Dict[str, str], expected: Dict[str, str]) -> Dict[str, str]:
    return {
        "field": expected["field"],
        "value": expected["value"],
        "expected_case_id": expected["case_id"],
        "actual_case_id": actual["case_id"],
    }


def _string_list(value: Any) -> List[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _expected_count(task: EvalTask) -> int:
    scope = _string_list(task.reference.get("expected_scope"))
    return len(_flatten_expected(task.reference.get("case_fact_map", {}), scope))


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return round(2 * precision * recall / (precision + recall), 6) if precision + recall else 0.0
