"""Diagnose latency and stability of the external RAG retrieval path.

The script first calls RAG /retrieve directly for several rounds. It then
optionally calls the same retrieval through the Python mid-layer. This makes
it possible to distinguish RAG cold-start/search latency from forwarding
overhead in the mid-layer.

Only Python's standard library is required.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUERY = "危险驾驶，酒精含量251.45mg/100ml，发生事故并负全部责任"

if os.name == "nt":
    # PowerShell may otherwise expose a legacy code page to Python, which makes
    # Chinese diagnostics unreadable in redirected logs.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


@dataclass
class ProbeResult:
    target: str
    round: int
    success: bool
    duration_ms: int
    status_code: Optional[int] = None
    evidence_count: Optional[int] = None
    response_bytes: Optional[int] = None
    error: Optional[str] = None
    health_after: Optional[bool] = None
    process: Optional[Dict[str, Any]] = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare direct RAG latency with the Python mid-layer path."
    )
    parser.add_argument("--rag-url", default="http://127.0.0.1:8001")
    parser.add_argument("--mid-url", default="http://127.0.0.1:8000")
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--mode", default="hybrid")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="Seconds to wait between requests.",
    )
    parser.add_argument(
        "--skip-mid",
        action="store_true",
        help="Only call RAG /retrieve directly.",
    )
    parser.add_argument(
        "--internal-token",
        default="",
        help="Mid-layer INTERNAL_SERVICE_TOKEN. Defaults to mid-layer/.env.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional report path. Defaults to debug/results/rag_diagnostic_*.json.",
    )
    return parser.parse_args()


def read_env_value(path: Path, name: str) -> str:
    if not path.is_file():
        return ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() != name:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        return value
    return ""


def request_json(
    url: str,
    *,
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int,
) -> tuple[bool, int, Optional[int], Optional[Dict[str, Any]], int, Optional[str]]:
    method = "POST" if payload is not None else "GET"
    body = None
    request_headers = dict(headers or {})
    request_headers.setdefault("Accept", "application/json")
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=body,
        headers=request_headers,
        method=method,
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            duration_ms = round((time.perf_counter() - started) * 1000)
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
            if not isinstance(parsed, dict):
                parsed = {"value": parsed}
            return True, duration_ms, response.status, parsed, len(raw), None
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        duration_ms = round((time.perf_counter() - started) * 1000)
        detail = raw.decode("utf-8", errors="replace")[:1000]
        return False, duration_ms, exc.code, None, len(raw), detail or str(exc)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        duration_ms = round((time.perf_counter() - started) * 1000)
        return False, duration_ms, None, None, 0, str(exc)


def health_ok(url: str, timeout: int = 3) -> bool:
    ok, _, status, data, _, _ = request_json(url, timeout=timeout)
    if not ok or status != 200 or not isinstance(data, dict):
        return False
    return data.get("status") == "ok"


def windows_process_snapshot(port: int) -> Optional[Dict[str, Any]]:
    if os.name != "nt":
        return None
    try:
        netstat = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        pid: Optional[int] = None
        for line in netstat.stdout.splitlines():
            columns = line.split()
            if len(columns) < 5 or columns[0].upper() != "TCP":
                continue
            local_address, state, candidate_pid = columns[1], columns[3], columns[4]
            if local_address.endswith(f":{port}") and state.upper() == "LISTENING":
                pid = int(candidate_pid)
                break
        if pid is None:
            return None
        command = (
            "$proc=Get-Process -Id "
            + str(pid)
            + " -ErrorAction SilentlyContinue;"
            + "if($proc){[pscustomobject]@{pid=$proc.Id;"
            + "memoryMB=[math]::Round($proc.WorkingSet64/1MB,2);"
            + "cpuSeconds=[math]::Round($proc.CPU,2)}|ConvertTo-Json -Compress}"
        )
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        output = completed.stdout.strip()
        if not output:
            return None
        value = json.loads(output)
        return value if isinstance(value, dict) else None
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


def run_direct(args: argparse.Namespace) -> List[ProbeResult]:
    results: List[ProbeResult] = []
    payload = {"query": args.query, "mode": args.mode, "top_k": args.top_k}
    endpoint = args.rag_url.rstrip("/") + "/retrieve"
    health_url = args.rag_url.rstrip("/") + "/health"
    for round_number in range(1, args.rounds + 1):
        ok, duration, status, data, size, error = request_json(
            endpoint,
            payload=payload,
            timeout=args.timeout,
        )
        evidence = data.get("evidence") if isinstance(data, dict) else None
        result = ProbeResult(
            target="rag_direct",
            round=round_number,
            success=ok,
            duration_ms=duration,
            status_code=status,
            evidence_count=len(evidence) if isinstance(evidence, list) else None,
            response_bytes=size,
            error=error,
            health_after=health_ok(health_url),
            process=windows_process_snapshot(8001),
        )
        results.append(result)
        print_result(result)
        if round_number < args.rounds:
            time.sleep(args.interval)
    return results


def run_mid(args: argparse.Namespace, token: str) -> List[ProbeResult]:
    results: List[ProbeResult] = []
    endpoint = args.mid_url.rstrip("/") + "/internal/knowledge/search"
    health_url = args.mid_url.rstrip("/") + "/health/live"
    headers = {"Authorization": f"Bearer {token}"}
    for round_number in range(1, args.rounds + 1):
        payload = {
            "requestId": f"rag-diagnostic-{round_number}",
            "toolCallId": f"rag-diagnostic-tool-{round_number}",
            "query": args.query,
            "mode": args.mode,
            "limit": args.top_k,
        }
        ok, duration, status, data, size, error = request_json(
            endpoint,
            payload=payload,
            headers=headers,
            timeout=args.timeout,
        )
        evidence = data.get("evidence") if isinstance(data, dict) else None
        result = ProbeResult(
            target="mid_layer",
            round=round_number,
            success=ok,
            duration_ms=duration,
            status_code=status,
            evidence_count=len(evidence) if isinstance(evidence, list) else None,
            response_bytes=size,
            error=error,
            health_after=health_ok(health_url),
            process=windows_process_snapshot(8000),
        )
        results.append(result)
        print_result(result)
        if round_number < args.rounds:
            time.sleep(args.interval)
    return results


def print_result(result: ProbeResult) -> None:
    memory = "-"
    if result.process and result.process.get("memoryMB") is not None:
        memory = f"{result.process['memoryMB']} MB"
    status = "OK" if result.success else "FAIL"
    health = "ok" if result.health_after else "down"
    evidence = result.evidence_count if result.evidence_count is not None else "-"
    print(
        f"[{result.target} {result.round}] {status} "
        f"{result.duration_ms} ms, evidence={evidence}, "
        f"health={health}, memory={memory}"
    )
    if result.error:
        print(f"  error: {result.error}")


def successful_durations(results: List[ProbeResult]) -> List[int]:
    return [item.duration_ms for item in results if item.success]


def median_or_none(values: List[int]) -> Optional[float]:
    return round(float(statistics.median(values)), 2) if values else None


def analyse(direct: List[ProbeResult], mid: List[ProbeResult]) -> Dict[str, Any]:
    findings: List[str] = []
    direct_success = [item for item in direct if item.success]
    direct_durations = successful_durations(direct)
    warm_durations = [item.duration_ms for item in direct_success[1:]]
    warm_median = median_or_none(warm_durations)

    if not direct_success:
        findings.append("RAG 直连请求全部失败，先恢复 RAG 服务，暂时不能判断检索性能。")
    else:
        first = direct_success[0].duration_ms
        if warm_median is not None and first >= max(3000, warm_median * 2, warm_median + 5000):
            findings.append(
                "首次直连明显慢于后续请求，符合 Embedding 模型或索引冷启动特征。"
            )
        if warm_median is not None and warm_median >= 5000:
            findings.append(
                "RAG 预热后的中位耗时仍超过 5 秒，需继续检查向量扫描、数据库和检索实现。"
            )
        if any(not item.success for item in direct[1:]):
            findings.append(
                "RAG 首次请求后出现失败，需要检查 RAG 进程退出、内存或 CUDA 异常。"
            )
        if any(item.health_after is False for item in direct):
            findings.append("请求后 RAG 健康检查失败，存在服务稳定性问题。")

    mid_durations = successful_durations(mid)
    if mid:
        if not mid_durations:
            findings.append("中台转发请求全部失败，请检查中台状态和内部服务令牌。")
        elif direct_durations:
            direct_reference = median_or_none(direct_durations[1:] or direct_durations)
            mid_reference = median_or_none(mid_durations)
            if (
                direct_reference is not None
                and mid_reference is not None
                and mid_reference - direct_reference >= 1000
            ):
                findings.append("中台路径比直连 RAG 多出至少 1 秒，需要检查中台转发链路。")
            else:
                findings.append("中台未表现出明显额外延迟，主要耗时更可能位于 RAG。")

    if not findings:
        findings.append("本次未发现明显冷启动、持续高延迟或服务退出，需要结合 RAG 分段日志继续定位。")

    return {
        "direct": {
            "success": len(direct_success),
            "total": len(direct),
            "first_success_ms": direct_success[0].duration_ms if direct_success else None,
            "warm_median_ms": warm_median,
            "all_success_median_ms": median_or_none(direct_durations),
        },
        "mid_layer": {
            "success": len(mid_durations),
            "total": len(mid),
            "median_ms": median_or_none(mid_durations),
        },
        "findings": findings,
    }


def report_path(value: str) -> Path:
    if value:
        return Path(value).resolve()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return PROJECT_ROOT / "debug" / "results" / f"rag_diagnostic_{stamp}.json"


def main() -> int:
    args = parse_args()
    if args.rounds < 2:
        print("--rounds must be at least 2 to identify cold-start behavior.", file=sys.stderr)
        return 2
    if not 1 <= args.top_k <= 20:
        print("--top-k must be between 1 and 20.", file=sys.stderr)
        return 2

    rag_health_url = args.rag_url.rstrip("/") + "/health"
    print(f"RAG health: {rag_health_url}")
    if not health_ok(rag_health_url):
        print("RAG is not healthy. Start it before running this diagnostic.", file=sys.stderr)
        return 1

    print("\nPhase 1: direct RAG requests")
    direct = run_direct(args)

    mid: List[ProbeResult] = []
    if not args.skip_mid:
        mid_health_url = args.mid_url.rstrip("/") + "/health/live"
        if health_ok(mid_health_url):
            token = (
                args.internal_token
                or os.getenv("INTERNAL_SERVICE_TOKEN", "").strip()
                or read_env_value(PROJECT_ROOT / "mid-layer" / ".env", "INTERNAL_SERVICE_TOKEN")
                or "development-internal-token"
            )
            print("\nPhase 2: requests through Python mid-layer")
            mid = run_mid(args, token)
        else:
            print("\nPhase 2 skipped: Python mid-layer is not healthy.")

    analysis = analyse(direct, mid)
    output = report_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "configuration": {
            "rag_url": args.rag_url,
            "mid_url": args.mid_url,
            "query_length": len(args.query),
            "mode": args.mode,
            "top_k": args.top_k,
            "rounds": args.rounds,
            "timeout_seconds": args.timeout,
        },
        "direct_results": [asdict(item) for item in direct],
        "mid_results": [asdict(item) for item in mid],
        "analysis": analysis,
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nAnalysis")
    for finding in analysis["findings"]:
        print(f"- {finding}")
    print(f"\nReport: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
