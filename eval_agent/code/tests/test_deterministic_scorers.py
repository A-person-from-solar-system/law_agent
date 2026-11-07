import json
import unittest

from eval_agent.code.agent_client import AgentClient, extract_source_ids
from eval_agent.code.models import EvalTask, RunResult
from eval_agent.code.reporter import build_report
from eval_agent.code.scorers.source_scorer import score_source_traceability
from eval_agent.code.scorers.tool_call_scorer import score_tool_call


def task(should_call=None):
    return EvalTask(
        task_id="task-1",
        dataset_name="test.jsonl",
        prompt="test",
        active_case=None,
        reference={},
        metric_types=[],
        should_call_rag=should_call,
    )


def run(**overrides):
    values = {
        "run_id": "run-1",
        "task_id": "task-1",
        "dataset_name": "test.jsonl",
        "status": "completed",
    }
    values.update(overrides)
    return RunResult(**values)


class DeterministicScorerTests(unittest.TestCase):
    def test_extracts_known_and_explicit_source_ids(self) -> None:
        answer = "依据 cail_001::chunk_0，另见 sourceId: fake-source-1。"
        found = extract_source_ids(answer, ["cail_001::chunk_0"])
        self.assertEqual(found, ["cail_001::chunk_0", "fake-source-1"])

    def test_does_not_extract_prefix_from_unicode_known_source_id(self) -> None:
        source_id = "judgment_孙某职务侵占罪刑事通知书"
        answer = f"参考 sourceId: {source_id}。"
        self.assertEqual(extract_source_ids(answer, [source_id]), [source_id])

    def test_collects_and_deduplicates_rag_evidence_from_run_messages(self) -> None:
        result = run()
        evidence = {
            "sourceId": "cail_001::chunk_0",
            "sourceType": "case",
            "excerpt": "类案事实",
            "sourceMetadata": {"imprisonment_months": 2, "punish_of_money": 1000},
        }
        tool_result = {
            "role": "toolResult",
            "toolName": "search_legal_kb",
            "isError": False,
            "content": [
                {"type": "text", "text": json.dumps({"evidence": [evidence]})}
            ],
        }
        AgentClient._collect_rag_evidence(result, [tool_result, tool_result])
        result.rag_evidence = AgentClient._unique_evidence(result.rag_evidence)
        self.assertEqual(result.rag_evidence, [evidence])

    def test_source_traceability_detects_invalid_citation(self) -> None:
        result = run(
            tool_called=True,
            rag_source_ids=["cail_001::chunk_0"],
            answer_source_ids=["cail_001::chunk_0", "fake-source-1"],
        )
        score = score_source_traceability(task(), result)
        self.assertEqual(score["score"], 0.5)
        self.assertEqual(score["invalid_citations"], ["fake-source-1"])

    def test_tool_call_confusion_outcomes(self) -> None:
        self.assertEqual(score_tool_call(task(True), run(tool_called=True))["outcome"], "true_positive")
        self.assertEqual(score_tool_call(task(False), run(tool_called=True))["outcome"], "false_positive")
        self.assertEqual(score_tool_call(task(True), run(tool_called=False))["outcome"], "false_negative")
        self.assertEqual(score_tool_call(task(False), run(tool_called=False))["outcome"], "true_negative")

    def test_report_aggregates_tool_metrics(self) -> None:
        scores = []
        for index, outcome in enumerate(
            ["true_positive", "true_negative", "false_positive", "false_negative"]
        ):
            scores.append(
                {
                    "task_id": str(index),
                    "run_status": "completed",
                    "scores": {"tool_call": {"status": "scored", "outcome": outcome}},
                }
            )
        report = build_report("run-1", scores, [{"status": "completed"}] * 4)
        tool = report["metrics"]["tool_call"]
        self.assertEqual(tool["accuracy"], 0.5)
        self.assertEqual(tool["precision"], 0.5)
        self.assertEqual(tool["recall"], 0.5)


if __name__ == "__main__":
    unittest.main()
