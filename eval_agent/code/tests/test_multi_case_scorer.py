import json
import unittest

from eval_agent.code.models import EvalTask, RunResult
from eval_agent.code.reporter import build_report
from eval_agent.code.scorers.multi_case_scorer import score_multi_case


def make_task(scope=None):
    return EvalTask(
        task_id="multi-1",
        dataset_name="multitask_eval.jsonl",
        prompt="extract",
        active_case=None,
        reference={
            "expected_scope": scope or ["case_A", "case_B"],
            "case_fact_map": {
                "case_A": {
                    "facts": {
                        "person": ["王某"],
                        "numbers": ["酒精含量=251.45mg/100ml"],
                    }
                },
                "case_B": {
                    "facts": {
                        "person": ["李某"],
                        "numbers": ["盗窃金额=5万元"],
                    }
                },
            },
        },
        metric_types=["multi_case"],
        metadata={"category": "same_cause"},
    )


def make_run(cases):
    return RunResult(
        run_id="run-1",
        task_id="multi-1",
        dataset_name="multitask_eval.jsonl",
        status="completed",
        answer=json.dumps({"cases": cases}, ensure_ascii=False),
    )


class MultiCaseScorerTests(unittest.TestCase):
    def test_scores_all_cases_by_fact_element(self):
        run = make_run(
            [
                {"caseId": "case_A", "facts": {"person": ["王某"], "numbers": ["251.45mg/100ml"]}},
                {"caseId": "case_B", "facts": {"person": ["李某"], "numbers": ["5万元"]}},
            ]
        )
        score = score_multi_case(make_task(), run, None)
        self.assertEqual(score["f1"], 1.0)
        self.assertEqual(score["confusion_rate"], 0.0)
        self.assertTrue(score["passed"])

    def test_detects_fact_assigned_to_wrong_case(self):
        run = make_run(
            [
                {"caseId": "case_A", "facts": {"person": ["李某"]}},
                {"caseId": "case_B", "facts": {"person": ["王某"]}},
            ]
        )
        score = score_multi_case(make_task(), run, None)
        self.assertEqual(score["misattributed_fact_count"], 2)
        self.assertEqual(score["confusion_rate"], 1.0)
        self.assertFalse(score["passed"])

    def test_targeted_case_penalizes_non_target_output(self):
        run = make_run(
            [
                {"caseId": "case_A", "facts": {"person": ["王某"]}},
                {"caseId": "case_B", "facts": {"person": ["李某"], "numbers": ["5万元"]}},
            ]
        )
        score = score_multi_case(make_task(["case_B"]), run, None)
        self.assertEqual(score["non_target_fact_count"], 1)
        self.assertGreater(score["non_target_leakage_rate"], 0)
        self.assertFalse(score["passed"])

    def test_normalizes_common_legal_fact_phrasing(self):
        task = make_task(["case_A"])
        task.reference["case_fact_map"]["case_A"]["facts"] = {
            "behavior": ["醉酒驾驶机动车"],
            "responsibility": ["承担事故全部责任"],
            "consequence": ["完成毒品交易或查获毒品"],
        }
        run = make_run(
            [
                {
                    "caseId": "case_A",
                    "facts": {
                        "behavior": ["醉酒后使用伪造驾驶证驾驶机动车"],
                        "responsibility": ["负本次事故全部责任"],
                        "consequence": ["成交后被公安人员当场抓获"],
                    },
                }
            ]
        )
        score = score_multi_case(task, run, None)
        self.assertEqual(score["f1"], 1.0)

    def test_report_uses_micro_averages(self):
        scores = [
            {
                "task_id": "1",
                "run_status": "completed",
                "scores": {
                    "multi_case": {
                        "status": "scored",
                        "passed": True,
                        "true_positive": 3,
                        "expected_fact_count": 4,
                        "output_fact_count": 3,
                        "misattributed_fact_count": 0,
                        "non_target_fact_count": 0,
                        "category": "different_cause",
                    }
                },
            }
        ]
        report = build_report("run-1", scores, [{"status": "completed"}])
        multi = report["metrics"]["multi_case"]
        self.assertEqual(multi["precision"], 1.0)
        self.assertEqual(multi["recall"], 0.75)
        self.assertEqual(multi["f1"], 0.857143)


if __name__ == "__main__":
    unittest.main()
