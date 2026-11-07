from typing import Any, Dict

from ..models import EvalTask, RunResult


def score_source_traceability(task: EvalTask, run: RunResult) -> Dict[str, Any]:
    del task
    if run.status != "completed":
        return {"status": "not_scored", "reason": "agent_run_failed"}
    if not run.tool_called:
        return {"status": "not_applicable", "reason": "rag_not_called"}
    rag_ids = set(run.rag_source_ids)
    answer_ids = set(run.answer_source_ids)
    if not rag_ids:
        return {"status": "not_applicable", "reason": "rag_returned_no_sources"}
    if not answer_ids:
        return {
            "status": "scored",
            "score": 0.0,
            "valid_citations": [],
            "invalid_citations": [],
            "reason": "answer_has_no_source_id",
        }
    valid = sorted(answer_ids & rag_ids)
    invalid = sorted(answer_ids - rag_ids)
    return {
        "status": "scored",
        "score": round(len(valid) / len(answer_ids), 6),
        "valid_citations": valid,
        "invalid_citations": invalid,
        "rag_source_ids": sorted(rag_ids),
    }
