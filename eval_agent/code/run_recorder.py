import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


class RunRecorder:
    def __init__(self, runs_dir: Path, reports_dir: Path, run_id: str) -> None:
        self.run_id = run_id
        self.run_dir = runs_dir / run_id
        self.report_dir = reports_dir / run_id
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.report_dir.mkdir(parents=True, exist_ok=False)
        self.results_path = self.run_dir / "results.jsonl"

    @staticmethod
    def default_run_id() -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{timestamp}-{uuid.uuid4().hex[:8]}"

    def write_config(self, config: Dict[str, Any]) -> None:
        self._write_json(self.run_dir / "run_config.json", config)

    def append_result(self, result: Dict[str, Any]) -> None:
        with self.results_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")

    def write_scores(self, scores: Dict[str, Any]) -> Path:
        path = self.report_dir / "scores.json"
        self._write_json(path, scores)
        return path

    def write_summary(self, content: str) -> Path:
        path = self.report_dir / "summary.md"
        path.write_text(content, encoding="utf-8")
        return path

    @staticmethod
    def _write_json(path: Path, data: Dict[str, Any]) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
