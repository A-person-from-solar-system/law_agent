import copy
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .models import EvalTask


class DatasetError(ValueError):
    pass


class DatasetLoader:
    DEFAULT_DATASETS = (
        "tasks_eval_v1.jsonl",
        "multitask_eval.jsonl",
        "multitask_eval_10.jsonl",
        "tool_call_eval.jsonl",
    )

    def __init__(self, datasets_dir: Path) -> None:
        self.datasets_dir = datasets_dir
        base_rows = self._read_jsonl(datasets_dir / "tasks_eval_v1.jsonl")
        self.base_index = self._index_rows(base_rows, "tasks_eval_v1.jsonl")

    def load(self, dataset_names: Iterable[str]) -> List[EvalTask]:
        tasks: List[EvalTask] = []
        seen = set()
        for name in dataset_names:
            rows = self._read_jsonl(self.datasets_dir / name)
            for row in rows:
                task = self._hydrate(name, row)
                if task.task_id in seen:
                    raise DatasetError(f"Duplicate task_id across datasets: {task.task_id}")
                seen.add(task.task_id)
                tasks.append(task)
        return tasks

    @staticmethod
    def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
        if not path.is_file():
            raise DatasetError(f"Dataset does not exist: {path}")
        rows: List[Dict[str, Any]] = []
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not raw_line.strip():
                continue
            try:
                row = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise DatasetError(f"Invalid JSON at {path}:{line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise DatasetError(f"Expected object at {path}:{line_number}")
            rows.append(row)
        return rows

    @staticmethod
    def _index_rows(rows: Iterable[Dict[str, Any]], dataset_name: str) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            task_id = row.get("task_id")
            if not isinstance(task_id, str) or not task_id:
                raise DatasetError(f"Missing task_id in {dataset_name}")
            if task_id in result:
                raise DatasetError(f"Duplicate task_id in {dataset_name}: {task_id}")
            result[task_id] = row
        return result

    def _base_row(self, source_task_id: str) -> Dict[str, Any]:
        row = self.base_index.get(source_task_id)
        if row is None:
            raise DatasetError(f"Unknown source_task_id: {source_task_id}")
        return row

    @staticmethod
    def _case_name(row: Dict[str, Any]) -> str:
        tags = row.get("tags")
        if isinstance(tags, list) and tags:
            return str(tags[-1])
        return str(row.get("task_id", "评测案件"))

    def _single_active_case(self, row: Dict[str, Any], case_id: str) -> Dict[str, Any]:
        case_facts = row.get("input", {}).get("case_facts")
        if not isinstance(case_facts, str) or not case_facts.strip():
            raise DatasetError(f"Missing case_facts for {row.get('task_id')}")
        return {
            "caseId": case_id,
            "caseName": self._case_name(row),
            "structuredFacts": {"caseFacts": case_facts},
        }

    def _hydrate(self, dataset_name: str, row: Dict[str, Any]) -> EvalTask:
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise DatasetError(f"Missing task_id in {dataset_name}")
        if dataset_name == "tasks_eval_v1.jsonl":
            return self._hydrate_base(dataset_name, row)
        if dataset_name in {"multitask_eval.jsonl", "multitask_eval_10.jsonl"}:
            return self._hydrate_multi(dataset_name, row)
        if dataset_name == "tool_call_eval.jsonl":
            return self._hydrate_tool(dataset_name, row)
        raise DatasetError(f"Unsupported dataset: {dataset_name}")

    def _hydrate_base(self, dataset_name: str, row: Dict[str, Any]) -> EvalTask:
        prompt = row.get("input", {}).get("question")
        if not isinstance(prompt, str) or not prompt.strip():
            raise DatasetError(f"Missing question for {row.get('task_id')}")
        reference = copy.deepcopy(row.get("reference", {}))
        reference["facts"] = self._structured_facts(reference.get("fact_points", []))
        return EvalTask(
            task_id=row["task_id"],
            dataset_name=dataset_name,
            prompt=self._single_evaluation_prompt(prompt),
            active_case=self._single_active_case(row, row["task_id"]),
            reference=reference,
            metric_types=["fact", "source", "disposal"],
            should_call_rag=row.get("should_call_rag"),
            metadata={"tags": row.get("tags", []), "annotation_status": row.get("annotation_status")},
        )

    def _hydrate_multi(self, dataset_name: str, row: Dict[str, Any]) -> EvalTask:
        input_data = row.get("input", {})
        case_refs = input_data.get("cases")
        prompt = input_data.get("question")
        if not isinstance(case_refs, list) or len(case_refs) < 2:
            raise DatasetError(f"Multi-case task needs at least two cases: {row.get('task_id')}")
        if not isinstance(prompt, str) or not prompt.strip():
            raise DatasetError(f"Missing multi-case question: {row.get('task_id')}")

        hydrated_cases: List[Dict[str, Any]] = []
        resolved_fact_map: Dict[str, Any] = {}
        for case_ref in case_refs:
            case_id = case_ref.get("case_id")
            source_task_id = case_ref.get("source_task_id")
            if not isinstance(case_id, str) or not isinstance(source_task_id, str):
                raise DatasetError(f"Invalid case reference in {row.get('task_id')}")
            base = self._base_row(source_task_id)
            case_facts = base.get("input", {}).get("case_facts")
            hydrated_cases.append(
                {
                    "caseId": case_id,
                    "sourceTaskId": source_task_id,
                    "caseName": self._case_name(base),
                    "caseFacts": case_facts,
                }
            )
            resolved_fact_map[case_id] = {
                "source_task_id": source_task_id,
                "fact_points": copy.deepcopy(base.get("reference", {}).get("fact_points", [])),
                "facts": self._structured_facts(
                    base.get("reference", {}).get("fact_points", [])
                ),
                "disposal_points": copy.deepcopy(
                    base.get("reference", {}).get("disposal_points", [])
                ),
            }

        reference = copy.deepcopy(row.get("reference", {}))
        reference["case_fact_map"] = resolved_fact_map
        expected_scope = reference.get("expected_scope", [])
        if not isinstance(expected_scope, list) or not expected_scope:
            expected_scope = [case["caseId"] for case in hydrated_cases]
            reference["expected_scope"] = expected_scope
        return EvalTask(
            task_id=row["task_id"],
            dataset_name=dataset_name,
            prompt=self._multi_extraction_prompt(prompt, expected_scope),
            active_case={
                "caseId": row["task_id"],
                "caseName": "多案件评测",
                "structuredFacts": {"cases": hydrated_cases},
            },
            reference=reference,
            metric_types=["multi_case"],
            metadata={
                "category": row.get("category"),
                "tags": row.get("tags", []),
                "annotation_status": row.get("annotation_status"),
            },
        )

    @staticmethod
    def _single_evaluation_prompt(question: str) -> str:
        return (
            f"{question}\n"
            "请正常完成案件分析、法律依据引用和处置建议，并在回答末尾额外输出一个事实提取块。"
            "事实提取块必须使用 <FACTS_JSON> 和 </FACTS_JSON> 包裹，中间只能放合法 JSON，格式为："
            '<FACTS_JSON>{"facts":{"person":[],"time":[],"location":[],"behavior":[],'
            '"numbers":[],"responsibility":[],"consequence":[]}}</FACTS_JSON>。'
            "事实只能来自当前案件材料，不得从检索案例中提取，不得推测。person只填被告人或核心行为人；"
            "time和location只填主要案发时间、地点；behavior用一句短语概括核心行为；"
            "numbers只填决定案件性质或后果的关键数值；responsibility只填正式责任认定；"
            "consequence只填直接案件后果。每个字段最多一项，没有就输出空数组。"
        )

    @staticmethod
    def _structured_facts(fact_points: Any) -> Dict[str, List[str]]:
        fields = {
            "person": [],
            "time": [],
            "location": [],
            "behavior": [],
            "numbers": [],
            "responsibility": [],
            "consequence": [],
        }
        labels = {
            "涉案人员": "person",
            "时间": "time",
            "地点": "location",
            "行为": "behavior",
            "关键数值": "numbers",
            "责任": "responsibility",
            "案件后果": "consequence",
        }
        if not isinstance(fact_points, list):
            return fields
        for item in fact_points:
            if not isinstance(item, str) or "：" not in item:
                continue
            label, value = item.split("：", 1)
            field = labels.get(label.strip())
            value = value.strip()
            if (
                field
                and value
                and value not in {"不适用", "无", "未知"}
                and not value.startswith("原文未明确")
            ):
                fields[field].append(value)
        return fields

    @staticmethod
    def _multi_extraction_prompt(question: str, expected_scope: List[str]) -> str:
        targets = "、".join(str(item) for item in expected_scope)
        return (
            f"{question}\n"
            "这是多案件事实提取任务。请仅根据案件材料提取目标案件的事实，不进行法律分析，"
            "不调用知识库，不补充或推断材料中没有的信息。目标案件为："
            f"{targets}。只输出一个合法 JSON 对象，不要输出 Markdown 或解释。格式为："
            '{"cases":[{"caseId":"case_A","facts":{"person":[],"time":[],'
            '"location":[],"behavior":[],"numbers":[],"responsibility":[],'
            '"consequence":[]}}]}。按照核心事实口径提取：person只填被告人或核心行为人，'
            "不填证人、被害人；time和location只填主要案发时间、地点；behavior只用一句短语概括核心行为；"
            "numbers只填决定案件性质或后果的关键数值；responsibility只填正式责任认定；"
            "consequence只填直接案件后果。每个字段最多一项，没有就输出空数组；"
            "只输出目标案件，不输出其他案件。"
        )

    def _hydrate_tool(self, dataset_name: str, row: Dict[str, Any]) -> EvalTask:
        source_task_id = row.get("source_task_id")
        input_data = row.get("input", {})
        active_case = None
        base = None
        if isinstance(source_task_id, str):
            base = self._base_row(source_task_id)
            active_case = self._single_active_case(base, source_task_id)

        prompt = input_data.get("question")
        if not isinstance(prompt, str) or not prompt.strip():
            if base is not None and input_data.get("question_path") == "input.question":
                prompt = base.get("input", {}).get("question")
        if not isinstance(prompt, str) or not prompt.strip():
            raise DatasetError(f"Missing tool-call question: {row.get('task_id')}")

        should_call = row.get("should_call_rag")
        if not isinstance(should_call, bool):
            raise DatasetError(f"Missing should_call_rag: {row.get('task_id')}")
        return EvalTask(
            task_id=row["task_id"],
            dataset_name=dataset_name,
            prompt=prompt,
            active_case=active_case,
            reference={},
            metric_types=["tool_call"],
            should_call_rag=should_call,
            metadata={
                "category": row.get("category"),
                "reason": row.get("reason"),
                "source_task_id": source_task_id,
                "annotation_status": row.get("annotation_status"),
            },
        )
