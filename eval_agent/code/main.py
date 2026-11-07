import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from eval_agent.code.agent_client import AgentClient
    from eval_agent.code.config import load_config
    from eval_agent.code.dataset_loader import DatasetError, DatasetLoader
    from eval_agent.code.judge_client import JudgeClient
    from eval_agent.code.models import EvalTask, RunResult
    from eval_agent.code.reporter import build_report, render_markdown
    from eval_agent.code.run_recorder import RunRecorder
    from eval_agent.code.scorers import (
        score_disposal,
        score_facts,
        score_multi_case,
        score_source_traceability,
        score_tool_call,
    )
else:
    from .agent_client import AgentClient
    from .config import load_config
    from .dataset_loader import DatasetError, DatasetLoader
    from .judge_client import JudgeClient
    from .models import EvalTask, RunResult
    from .reporter import build_report, render_markdown
    from .run_recorder import RunRecorder
    from .scorers import (
        score_disposal,
        score_facts,
        score_multi_case,
        score_source_traceability,
        score_tool_call,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Law Agent offline evaluator")
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=list(DatasetLoader.DEFAULT_DATASETS),
        help="Dataset file names under eval_agent/datasets",
    )
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N tasks")
    parser.add_argument("--run-id", default=None, help="Custom run identifier")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and hydrate datasets without calling Agent",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config()
    try:
        tasks = DatasetLoader(config.datasets_dir).load(args.datasets)
    except DatasetError as exc:
        print(f"Dataset error: {exc}", file=sys.stderr)
        return 2
    if args.limit is not None:
        if args.limit < 1:
            print("--limit must be positive", file=sys.stderr)
            return 2
        tasks = tasks[: args.limit]

    if args.dry_run:
        print(f"Validated {len(tasks)} tasks from {len(args.datasets)} datasets.")
        for name in args.datasets:
            count = sum(1 for task in tasks if task.dataset_name == name)
            print(f"- {name}: {count}")
        return 0

    run_id = args.run_id or RunRecorder.default_run_id()
    recorder = RunRecorder(config.runs_dir, config.reports_dir, run_id)
    recorder.write_config(
        {
            "run_id": run_id,
            "datasets": args.datasets,
            "task_count": len(tasks),
            "config": config.public_dict(),
        }
    )
    agent = AgentClient(config)
    judge = JudgeClient(config)
    task_scores: List[Dict[str, Any]] = []
    run_results: List[Dict[str, Any]] = []

    for index, task in enumerate(tasks, 1):
        print(f"[{index}/{len(tasks)}] {task.task_id}")
        result = agent.run(run_id, task)
        result_data = result.to_dict()
        result_data["input"] = {
            "prompt": task.prompt,
            "active_case": task.active_case,
        }
        recorder.append_result(result_data)
        run_results.append(result_data)
        task_scores.append(score_task(task, result, judge))

    report = build_report(run_id, task_scores, run_results)
    scores_path = recorder.write_scores(report)
    summary_path = recorder.write_summary(render_markdown(report))
    print(f"Run results: {recorder.results_path}")
    print(f"Scores: {scores_path}")
    print(f"Summary: {summary_path}")
    return 0


def score_task(task: EvalTask, result: RunResult, judge: JudgeClient) -> Dict[str, Any]:
    scores: Dict[str, Any] = {}
    if "fact" in task.metric_types:
        scores["fact"] = score_facts(task, result, judge)
    if "source" in task.metric_types:
        scores["source"] = score_source_traceability(task, result)
    if "disposal" in task.metric_types:
        scores["disposal"] = score_disposal(task, result, judge)
    if "multi_case" in task.metric_types:
        scores["multi_case"] = score_multi_case(task, result, judge)
    if "tool_call" in task.metric_types:
        scores["tool_call"] = score_tool_call(task, result)
    return {
        "task_id": task.task_id,
        "dataset_name": task.dataset_name,
        "run_status": result.status,
        "error_code": result.error_code,
        "error_message": result.error_message,
        "scores": scores,
    }


if __name__ == "__main__":
    raise SystemExit(main())
