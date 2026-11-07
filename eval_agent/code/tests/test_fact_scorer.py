import unittest

from eval_agent.code.models import EvalTask, RunResult
from eval_agent.code.scorers.fact_scorer import score_facts


class FactScorerTests(unittest.TestCase):
    @staticmethod
    def _task() -> EvalTask:
        return EvalTask(
            task_id="case_1",
            dataset_name="test.jsonl",
            prompt="test",
            active_case=None,
            reference={
                "facts": {
                    "person": ["王某某"],
                    "time": ["2017年2月1日18时许"],
                    "location": ["幸福大道延长线路口"],
                    "behavior": ["醉酒驾驶机动车"],
                    "numbers": ["酒精含量=251.45mg/100ml"],
                    "responsibility": ["承担事故全部责任"],
                    "consequence": ["车辆受损"],
                }
            },
            metric_types=["fact"],
        )

    @staticmethod
    def _run(answer: str) -> RunResult:
        return RunResult(
            run_id="run_1",
            task_id="case_1",
            dataset_name="test.jsonl",
            status="completed",
            answer=answer,
        )

    def test_scores_structured_fact_block_without_judge(self) -> None:
        answer = """案件分析正文。\n<FACTS_JSON>{"facts":{"person":["王某某"],"time":["2017年2月1日18时"],"location":["幸福大道延长线路口"],"behavior":["酒后驾驶机动车"],"numbers":["251.45mg/100ml"],"responsibility":["负事故全部责任"],"consequence":["车辆损坏"]}}</FACTS_JSON>"""
        score = score_facts(self._task(), self._run(answer), None)
        self.assertEqual(score["f1"], 1.0)
        self.assertEqual(score["true_positive"], 7)

    def test_counts_missing_and_extra_facts(self) -> None:
        answer = """<FACTS_JSON>{"facts":{"person":["李某"],"time":[],"location":[],"behavior":[],"numbers":[],"responsibility":[],"consequence":[]}}</FACTS_JSON>"""
        score = score_facts(self._task(), self._run(answer), None)
        self.assertEqual(score["true_positive"], 0)
        self.assertEqual(score["false_positive"], 1)
        self.assertEqual(score["false_negative"], 7)

    def test_invalid_fact_block_is_zero_scored(self) -> None:
        score = score_facts(self._task(), self._run("只有分析正文"), None)
        self.assertEqual(score["f1"], 0.0)
        self.assertEqual(score["reason"], "invalid_structured_output")


if __name__ == "__main__":
    unittest.main()
