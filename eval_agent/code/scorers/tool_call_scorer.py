from typing import Any, Dict

from ..models import EvalTask, RunResult


def score_tool_call(task: EvalTask, run: RunResult) -> Dict[str, Any]:
    if task.should_call_rag is None:
        return {"status": "not_scored", "reason": "missing_expected_label"}
    if run.status != "completed":
        return {"status": "not_scored", "reason": "agent_run_failed"}
    expected = task.should_call_rag
    actual = run.tool_called
    if expected and actual:
        outcome = "true_positive"
    elif not expected and actual:
        outcome = "false_positive"
    elif expected and not actual:
        outcome = "false_negative"
    else:
        outcome = "true_negative"
    return {
        "status": "scored",
        "passed": expected == actual,
        "score": 1.0 if expected == actual else 0.0,
        "expected_call": expected,
        "actual_call": actual,
        "outcome": outcome,
    }
