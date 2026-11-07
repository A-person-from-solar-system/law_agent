from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EvalTask:
    task_id: str
    dataset_name: str
    prompt: str
    active_case: Optional[Dict[str, Any]]
    reference: Dict[str, Any]
    metric_types: List[str]
    should_call_rag: Optional[bool] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunResult:
    run_id: str
    task_id: str
    dataset_name: str
    status: str
    answer: str = ""
    tool_called: bool = False
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    rag_evidence: List[Dict[str, Any]] = field(default_factory=list)
    rag_source_ids: List[str] = field(default_factory=list)
    answer_source_ids: List[str] = field(default_factory=list)
    usage: Dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
