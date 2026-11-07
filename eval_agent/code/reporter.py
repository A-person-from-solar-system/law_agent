from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


def build_report(
    run_id: str,
    task_scores: List[Dict[str, Any]],
    run_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task_count": len(task_scores),
        "run_summary": _run_summary(run_results),
        "metrics": {
            "fact": _average_metric(task_scores, "fact", "f1"),
            "source": _average_metric(task_scores, "source", "score"),
            "disposal": _average_metric(task_scores, "disposal", "score"),
            "multi_case": _multi_summary(task_scores),
            "tool_call": _tool_summary(task_scores),
        },
        "tasks": task_scores,
    }


def render_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# Agent 离线评测报告",
        "",
        f"- Run ID：`{report['run_id']}`",
        f"- Task 数量：{report['task_count']}",
        f"- 成功运行：{report['run_summary']['completed']}",
        f"- 运行失败：{report['run_summary']['failed']}",
        "",
        "## 指标汇总",
        "",
        "| 指标 | 得分 | 已评分 Task |",
        "| --- | ---: | ---: |",
    ]
    metrics = report["metrics"]
    lines.extend(
        [
            _metric_row("事实识别 F1", metrics["fact"]),
            _metric_row("来源可追溯性", metrics["source"]),
            _metric_row("处置建议合理性", metrics["disposal"]),
            _metric_row("多案件事实提取 F1", metrics["multi_case"], "f1"),
            _metric_row("多案件 Task 通过率", metrics["multi_case"], "accuracy"),
            _metric_row("工具调用准确率", metrics["tool_call"], "accuracy"),
        ]
    )

    tool = metrics["tool_call"]
    multi = metrics["multi_case"]
    lines.extend(
        [
            "",
            "## 过程指标",
            "",
            f"- 工具调用精确率：{_format_score(tool.get('precision'))}",
            f"- 工具调用召回率：{_format_score(tool.get('recall'))}",
            f"- 工具误调率：{_format_score(tool.get('false_positive_rate'))}",
            f"- 工具漏调率：{_format_score(tool.get('false_negative_rate'))}",
            f"- 多案件事实提取精确率：{_format_score(multi.get('precision'))}",
            f"- 多案件事实提取召回率：{_format_score(multi.get('recall'))}",
            f"- 跨案件事实混淆率：{_format_score(multi.get('confusion_rate'))}",
            f"- 非目标案件事实泄漏率：{_format_score(multi.get('non_target_leakage_rate'))}",
            "",
            "## 运行失败",
            "",
        ]
    )
    failures = [item for item in report["tasks"] if item.get("run_status") != "completed"]
    if not failures:
        lines.append("无。")
    else:
        for item in failures:
            lines.append(
                f"- `{item['task_id']}`：{item.get('error_code') or 'UNKNOWN'} "
                f"{item.get('error_message') or ''}".rstrip()
            )
    lines.append("")
    lines.append("> 事实识别和多案件事实提取由规则评分；未配置评分模型时，仅处置建议显示为未评分。")
    lines.append("")
    return "\n".join(lines)


def _run_summary(results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = list(results)
    errors = Counter(
        str(row.get("error_code"))
        for row in rows
        if row.get("status") != "completed" and row.get("error_code")
    )
    return {
        "completed": sum(1 for row in rows if row.get("status") == "completed"),
        "failed": sum(1 for row in rows if row.get("status") != "completed"),
        "error_distribution": dict(errors),
    }


def _average_metric(
    task_scores: Iterable[Dict[str, Any]], metric_name: str, value_name: str
) -> Dict[str, Any]:
    values: List[float] = []
    for task in task_scores:
        metric = task.get("scores", {}).get(metric_name)
        if isinstance(metric, dict) and metric.get("status") == "scored":
            value = metric.get(value_name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.append(float(value))
    return {
        "score": round(sum(values) / len(values), 6) if values else None,
        "scored_tasks": len(values),
    }


def _multi_summary(task_scores: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    metrics = _scored_metrics(task_scores, "multi_case")
    true_positive = sum(int(item.get("true_positive", 0)) for item in metrics)
    expected_count = sum(int(item.get("expected_fact_count", 0)) for item in metrics)
    output_count = sum(int(item.get("output_fact_count", 0)) for item in metrics)
    misattributed = sum(int(item.get("misattributed_fact_count", 0)) for item in metrics)
    non_target = sum(int(item.get("non_target_fact_count", 0)) for item in metrics)
    precision = _ratio(true_positive, output_count)
    recall = _ratio(true_positive, expected_count)
    f1 = (
        round(2 * precision * recall / (precision + recall), 6)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    by_category: Dict[str, Dict[str, Any]] = {}
    categories = sorted({str(item.get("category")) for item in metrics if item.get("category")})
    for category in categories:
        rows = [item for item in metrics if item.get("category") == category]
        by_category[category] = {
            "accuracy": _ratio(sum(1 for item in rows if item.get("passed")), len(rows)),
            "scored_tasks": len(rows),
        }
    return {
        "accuracy": round(sum(1 for item in metrics if item.get("passed")) / len(metrics), 6)
        if metrics
        else None,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_rate": _ratio(misattributed, output_count),
        "non_target_leakage_rate": _ratio(non_target, output_count),
        "counts": {
            "true_positive": true_positive,
            "expected": expected_count,
            "output": output_count,
            "misattributed": misattributed,
            "non_target": non_target,
        },
        "by_category": by_category,
        "scored_tasks": len(metrics),
    }


def _tool_summary(task_scores: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    metrics = _scored_metrics(task_scores, "tool_call")
    counts = Counter(str(item.get("outcome")) for item in metrics)
    tp = counts["true_positive"]
    tn = counts["true_negative"]
    fp = counts["false_positive"]
    fn = counts["false_negative"]
    return {
        "accuracy": _ratio(tp + tn, tp + tn + fp + fn),
        "precision": _ratio(tp, tp + fp),
        "recall": _ratio(tp, tp + fn),
        "false_positive_rate": _ratio(fp, fp + tn),
        "false_negative_rate": _ratio(fn, fn + tp),
        "counts": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "scored_tasks": len(metrics),
    }


def _scored_metrics(
    task_scores: Iterable[Dict[str, Any]], metric_name: str
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for task in task_scores:
        metric = task.get("scores", {}).get(metric_name)
        if isinstance(metric, dict) and metric.get("status") == "scored":
            result.append(metric)
    return result


def _ratio(numerator: int, denominator: int) -> Optional[float]:
    return round(numerator / denominator, 6) if denominator else None


def _format_score(value: Any) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "未评分"
    return f"{float(value):.2%}"


def _metric_row(label: str, metric: Dict[str, Any], key: str = "score") -> str:
    return f"| {label} | {_format_score(metric.get(key))} | {metric.get('scored_tasks', 0)} |"
