import unittest
from pathlib import Path

from eval_agent.code.dataset_loader import DatasetLoader


class DatasetLoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.datasets_dir = Path(__file__).resolve().parents[2] / "datasets"
        cls.loader = DatasetLoader(cls.datasets_dir)

    def test_loads_all_current_datasets(self) -> None:
        tasks = self.loader.load(DatasetLoader.DEFAULT_DATASETS)
        self.assertEqual(len(tasks), 78)
        self.assertEqual(len({task.task_id for task in tasks}), 78)

    def test_hydrates_multi_case_references(self) -> None:
        tasks = self.loader.load(["multitask_eval_10.jsonl"])
        self.assertEqual(len(tasks), 3)
        for task in tasks:
            cases = task.active_case["structuredFacts"]["cases"]
            self.assertEqual(len(cases), 10)
            self.assertTrue(all(case["caseFacts"] for case in cases))
            self.assertEqual(len(task.reference["case_fact_map"]), 10)
            self.assertIn("只输出一个合法 JSON 对象", task.prompt)
            for case in task.reference["case_fact_map"].values():
                self.assertIn("facts", case)
                self.assertIn("person", case["facts"])

    def test_hydrates_single_case_structured_facts_and_prompt(self) -> None:
        task = self.loader.load(["tasks_eval_v1.jsonl"])[0]
        self.assertEqual(task.reference["facts"]["person"], ["王某某"])
        self.assertEqual(
            task.reference["facts"]["numbers"], ["酒精含量=251.45mg/100ml"]
        )
        self.assertIn("<FACTS_JSON>", task.prompt)
        self.assertIn("每个字段最多一项", task.prompt)

    def test_tool_dataset_is_balanced(self) -> None:
        tasks = self.loader.load(["tool_call_eval.jsonl"])
        positives = sum(task.should_call_rag is True for task in tasks)
        negatives = sum(task.should_call_rag is False for task in tasks)
        self.assertEqual((positives, negatives), (20, 20))
        self.assertTrue(all(task.prompt for task in tasks))


if __name__ == "__main__":
    unittest.main()
