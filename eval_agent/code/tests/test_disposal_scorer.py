import unittest

from eval_agent.code.models import EvalTask, RunResult
from eval_agent.code.scorers.disposal_scorer import score_disposal


class StubJudge:
    enabled = True

    def __init__(self):
        self.payload = None

    def evaluate(self, _system_prompt, payload):
        self.payload = payload
        return {
            "items": [
                {
                    "id": "offense_and_disposition",
                    "result": "pass",
                    "reason": "方向正确",
                },
                {
                    "id": "rag_evidence_use",
                    "result": "pass",
                    "reason": "引用并比较类案",
                },
                {"id": "key_factors", "result": "pass", "reason": "因素完整"},
                {
                    "id": "recommendation_quality",
                    "result": "fail",
                    "reason": "建议仍偏笼统",
                },
                {
                    "id": "uncertainty_and_consistency",
                    "result": "pass",
                    "reason": "边界清楚",
                },
            ],
            "severe_error": False,
            "severe_error_reason": "",
        }


class DisposalScorerTests(unittest.TestCase):
    def test_uses_rag_evidence_and_excludes_observed_outcome_from_judge(self):
        task = EvalTask(
            task_id="task-1",
            dataset_name="test.jsonl",
            prompt="分析案件",
            active_case={"structuredFacts": {"caseFacts": "案件事实"}},
            reference={
                "disposal_points": [
                    "罪名：危险驾驶罪",
                    "处置方式：拘役",
                    "刑期结果：4个月",
                    "罚金结果：0元",
                    "量刑考虑：醉酒程度、事故责任",
                ]
            },
            metric_types=["disposal"],
        )
        evidence = [
            {
                "sourceId": "cail_001::chunk_0",
                "sourceType": "case",
                "excerpt": "类案事实",
                "sourceMetadata": {"imprisonment_months": 2, "punish_of_money": 1000},
            }
        ]
        run = RunResult(
            run_id="run-1",
            task_id="task-1",
            dataset_name="test.jsonl",
            status="completed",
            answer="参考类案给出区间",
            rag_evidence=evidence,
        )
        judge = StubJudge()

        scored = score_disposal(task, run, judge)

        self.assertEqual(judge.payload["rag_evidence"], evidence)
        self.assertNotIn("observed_outcome", judge.payload)
        self.assertEqual(scored["observed_outcome"], {"sentence": "4个月", "fine": "0元"})
        self.assertEqual(scored["score"], 0.85)
        self.assertTrue(scored["passed"])


if __name__ == "__main__":
    unittest.main()
