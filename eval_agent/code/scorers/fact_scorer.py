import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from ..judge_client import JudgeClient
from ..models import EvalTask, RunResult
from .multi_case_scorer import facts_equivalent, flatten_fact_fields


def score_facts(task: EvalTask, run: RunResult, _judge: JudgeClient) -> Dict[str, Any]:
    """Use deterministic field matching instead of an LLM judge."""
    if run.status != "completed":
        return {"status": "not_scored", "reason": "agent_run_failed"}

    parsed, error = _parse_fact_block(run.answer)
    expected = flatten_fact_fields(task.task_id, task.reference.get("facts", {}))
    if error:
        return _invalid_output(len(expected), error)
    actual = flatten_fact_fields(task.task_id, parsed.get("facts"))

    matched_expected: Set[int] = set()
    matched_actual: Set[int] = set()
    correct: List[Dict[str, str]] = []
    for actual_index, actual_fact in enumerate(actual):
        for expected_index, expected_fact in enumerate(expected):
            if expected_index in matched_expected:
                continue
            if actual_fact["field"] != expected_fact["field"]:
                continue
            if not facts_equivalent(
                actual_fact["value"], expected_fact["value"], actual_fact["field"]
            ):
                continue
            matched_actual.add(actual_index)
            matched_expected.add(expected_index)
            correct.append(
                {
                    "field": expected_fact["field"],
                    "expected": expected_fact["value"],
                    "actual": actual_fact["value"],
                }
            )
            break

    missing = [fact for index, fact in enumerate(expected) if index not in matched_expected]
    extra = [fact for index, fact in enumerate(actual) if index not in matched_actual]
    tp = len(correct)
    fp = len(extra)
    fn = len(missing)
    precision = _ratio(tp, len(actual))
    recall = _ratio(tp, len(expected))
    f1 = _f1(precision, recall)
    return {
        "status": "scored",
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "expected_fact_count": len(expected),
        "output_fact_count": len(actual),
        "correct_facts": correct,
        "missing_facts": missing,
        "extra_facts": extra,
    }


def _parse_fact_block(answer: str) -> Tuple[Dict[str, Any], Optional[str]]:
    tagged = re.search(
        r"<FACTS_JSON>\s*(\{.*?\})\s*</FACTS_JSON>", answer, flags=re.DOTALL
    )
    candidates = [tagged.group(1)] if tagged else []
    if not candidates:
        candidates.extend(
            match.group(1)
            for match in re.finditer(
                r"```(?:json)?\s*(\{.*?\})\s*```", answer, flags=re.DOTALL
            )
        )
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("facts"), dict):
            return parsed, None
    return {}, "Agent 未返回包含 facts 对象的合法 FACTS_JSON 事实块"


def _invalid_output(expected_count: int, detail: str) -> Dict[str, Any]:
    return {
        "status": "scored",
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "true_positive": 0,
        "false_positive": 0,
        "false_negative": expected_count,
        "expected_fact_count": expected_count,
        "output_fact_count": 0,
        "correct_facts": [],
        "missing_facts": [],
        "extra_facts": [],
        "reason": "invalid_structured_output",
        "detail": detail,
    }


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 6)
