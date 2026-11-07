import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def _env_or(name: str, fallback: str) -> str:
    return os.getenv(name, "").strip() or fallback


@dataclass(frozen=True)
class EvalConfig:
    eval_root: Path
    datasets_dir: Path
    runs_dir: Path
    reports_dir: Path
    agent_url: str
    agent_token: str
    request_timeout_seconds: int
    judge_base_url: str
    judge_api_key: str
    judge_model: str
    judge_timeout_seconds: int

    @property
    def judge_enabled(self) -> bool:
        return bool(self.judge_base_url and self.judge_api_key and self.judge_model)

    def public_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["eval_root"] = str(self.eval_root)
        data["datasets_dir"] = str(self.datasets_dir)
        data["runs_dir"] = str(self.runs_dir)
        data["reports_dir"] = str(self.reports_dir)
        data["agent_token"] = "***" if self.agent_token else ""
        data["judge_api_key"] = "***" if self.judge_api_key else ""
        data["judge_enabled"] = self.judge_enabled
        return data


def load_config() -> EvalConfig:
    eval_root = Path(__file__).resolve().parents[1]
    repo_root = eval_root.parent
    _load_env_file(repo_root / "agent-engine" / ".env")
    _load_env_file(Path(__file__).resolve().parent / ".env")

    model_provider = os.getenv("MODEL_PROVIDER", "").strip().lower()
    default_judge_base_url = ""
    if model_provider == "deepseek":
        default_judge_base_url = "https://api.deepseek.com"
    elif model_provider == "openai":
        default_judge_base_url = "https://api.openai.com/v1"

    return EvalConfig(
        eval_root=eval_root,
        datasets_dir=eval_root / "datasets",
        runs_dir=eval_root / "runs",
        reports_dir=eval_root / "reports",
        agent_url=os.getenv(
            "EVAL_AGENT_URL", "http://127.0.0.1:3100/internal/v1/agent/runs"
        ).rstrip("/"),
        agent_token=os.getenv(
            "EVAL_AGENT_TOKEN", os.getenv("AGENT_ENGINE_SERVICE_TOKEN", "")
        ).strip(),
        request_timeout_seconds=int(os.getenv("EVAL_REQUEST_TIMEOUT_SECONDS", "240")),
        judge_base_url=_env_or("EVAL_JUDGE_BASE_URL", default_judge_base_url).rstrip("/"),
        judge_api_key=_env_or("EVAL_JUDGE_API_KEY", os.getenv("MODEL_API_KEY", "")),
        judge_model=_env_or("EVAL_JUDGE_MODEL", os.getenv("MODEL_ID", "")),
        judge_timeout_seconds=int(os.getenv("EVAL_JUDGE_TIMEOUT_SECONDS", "120")),
    )
