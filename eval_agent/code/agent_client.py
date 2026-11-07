import json
import re
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .config import EvalConfig
from .models import EvalTask, RunResult


class AgentClient:
    def __init__(self, config: EvalConfig) -> None:
        self.config = config

    def run(self, run_id: str, task: EvalTask) -> RunResult:
        request_id = f"eval-{uuid.uuid4().hex}"
        payload: Dict[str, Any] = {
            "requestId": request_id,
            "sessionId": f"eval-{task.task_id}-{uuid.uuid4().hex[:8]}",
            "prompt": task.prompt,
            "history": [],
        }
        if task.active_case is not None:
            payload["activeCase"] = task.active_case

        headers = {"Accept": "text/event-stream", "Content-Type": "application/json"}
        if self.config.agent_token:
            headers["Authorization"] = f"Bearer {self.config.agent_token}"
        request = urllib.request.Request(
            self.config.agent_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        started = time.monotonic()
        result = RunResult(
            run_id=run_id,
            task_id=task.task_id,
            dataset_name=task.dataset_name,
            status="failed",
        )
        text_parts: List[str] = []
        try:
            with urllib.request.urlopen(
                request, timeout=self.config.request_timeout_seconds
            ) as response:
                for event_name, data in self._iter_sse(response):
                    result.events.append({"event": event_name, "data": data})
                    if event_name == "text.delta":
                        delta = data.get("delta")
                        if isinstance(delta, str):
                            text_parts.append(delta)
                    elif event_name == "tool.started":
                        if data.get("toolName") == "search_legal_kb":
                            result.tool_called = True
                            result.tool_calls.append(
                                {
                                    "toolCallId": data.get("toolCallId"),
                                    "toolName": data.get("toolName"),
                                    "argumentsSafe": data.get("argumentsSafe"),
                                }
                            )
                    elif event_name == "tool.completed":
                        self._collect_tool_completion(result, data)
                    elif event_name == "usage":
                        result.usage = {
                            key: value
                            for key, value in data.items()
                            if key in {"inputTokens", "outputTokens", "totalTokens"}
                        }
                    elif event_name == "run.completed":
                        result.status = "completed"
                        self._collect_rag_evidence(result, data.get("newMessages"))
                        if not text_parts:
                            final_text = self._message_text(data.get("finalMessage"))
                            if final_text:
                                text_parts.append(final_text)
                    elif event_name == "run.failed":
                        result.status = "failed"
                        result.error_code = str(data.get("code", "AGENT_FAILED"))
                        result.error_message = str(data.get("message", "Agent run failed"))
        except urllib.error.HTTPError as exc:
            result.error_code = f"HTTP_{exc.code}"
            result.error_message = self._http_error_message(exc)
        except urllib.error.URLError as exc:
            result.error_code = "AGENT_CONNECTION_FAILED"
            result.error_message = str(exc.reason)
        except TimeoutError as exc:
            result.error_code = "AGENT_TIMEOUT"
            result.error_message = str(exc)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            result.error_code = "INVALID_AGENT_STREAM"
            result.error_message = str(exc)

        result.answer = "".join(text_parts).strip()
        result.rag_evidence = self._unique_evidence(result.rag_evidence)
        result.rag_source_ids = self._unique(result.rag_source_ids)
        result.answer_source_ids = extract_source_ids(result.answer, result.rag_source_ids)
        result.duration_ms = round((time.monotonic() - started) * 1000)
        if result.status != "completed" and not result.error_code:
            result.error_code = "INCOMPLETE_STREAM"
            result.error_message = "Agent stream ended without run.completed"
        return result

    @staticmethod
    def _iter_sse(response: Any) -> Iterable[Tuple[str, Dict[str, Any]]]:
        event_name: Optional[str] = None
        data_lines: List[str] = []
        for raw_line in response:
            line = raw_line.decode("utf-8").rstrip("\r\n")
            if line == "":
                if event_name and data_lines:
                    data = json.loads("\n".join(data_lines))
                    if not isinstance(data, dict):
                        raise ValueError("SSE data must be a JSON object")
                    yield event_name, data
                event_name = None
                data_lines = []
                continue
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        if event_name and data_lines:
            data = json.loads("\n".join(data_lines))
            if not isinstance(data, dict):
                raise ValueError("SSE data must be a JSON object")
            yield event_name, data

    @staticmethod
    def _collect_tool_completion(result: RunResult, data: Dict[str, Any]) -> None:
        if data.get("toolName") != "search_legal_kb":
            return
        tool_call_id = data.get("toolCallId")
        for call in result.tool_calls:
            if call.get("toolCallId") == tool_call_id:
                call["isError"] = bool(data.get("isError"))
                call["durationMs"] = data.get("durationMs")
                call["errorCode"] = data.get("errorCode")
                call["result"] = data.get("result")
                break
        details = data.get("result")
        if isinstance(details, dict) and isinstance(details.get("sourceIds"), list):
            result.rag_source_ids.extend(
                str(value) for value in details["sourceIds"] if isinstance(value, str)
            )

    @staticmethod
    def _message_text(message: Any) -> str:
        if not isinstance(message, dict):
            return ""
        content = message.get("content")
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return ""
        return "\n".join(
            str(item.get("text"))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text")
        )

    @staticmethod
    def _collect_rag_evidence(result: RunResult, messages: Any) -> None:
        """Extract the exact reduced evidence consumed by the Agent.

        The evaluator reads evidence already present in the internal run stream;
        this does not add evidence to the compact tool.completed payload.
        """
        if not isinstance(messages, list):
            return
        for message in messages:
            if not isinstance(message, dict):
                continue
            if message.get("role") != "toolResult":
                continue
            if message.get("toolName") != "search_legal_kb" or message.get("isError"):
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if not isinstance(item, dict) or item.get("type") != "text":
                    continue
                text = item.get("text")
                if not isinstance(text, str):
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    continue
                evidence = payload.get("evidence") if isinstance(payload, dict) else None
                if not isinstance(evidence, list):
                    continue
                for candidate in evidence:
                    if not isinstance(candidate, dict):
                        continue
                    source_id = candidate.get("sourceId")
                    if not isinstance(source_id, str) or not source_id:
                        continue
                    result.rag_evidence.append(candidate)

    @staticmethod
    def _unique_evidence(values: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unique: Dict[str, Dict[str, Any]] = {}
        for item in values:
            source_id = item.get("sourceId")
            if isinstance(source_id, str) and source_id and source_id not in unique:
                unique[source_id] = item
        return list(unique.values())

    @staticmethod
    def _http_error_message(exc: urllib.error.HTTPError) -> str:
        try:
            raw = exc.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("message"):
                return str(data["message"])
            return raw[:1000]
        except (OSError, ValueError, json.JSONDecodeError):
            return str(exc)

    @staticmethod
    def _unique(values: Iterable[str]) -> List[str]:
        return list(dict.fromkeys(values))


def extract_source_ids(answer: str, known_source_ids: Iterable[str]) -> List[str]:
    found: List[str] = []
    remaining = answer
    for source_id in sorted(set(known_source_ids), key=len, reverse=True):
        if source_id and source_id in answer:
            found.append(source_id)
            # Avoid extracting a partial token such as `judgment_` from an
            # already matched Unicode source ID.
            remaining = remaining.replace(source_id, " ")

    patterns = (
        r"(?:sourceId|source_id)\s*[：:=]\s*[`\"']?([\w][\w.:-]{2,255})",
        r"\b(cail_[A-Za-z0-9_-]+(?:::[A-Za-z0-9_.:-]+)?)\b",
        r"\b((?:law|case)-[A-Za-z0-9_.:-]+)\b",
        r"\b((?:entity|relation|community)::[A-Za-z0-9_.:-]+)\b",
    )
    for pattern in patterns:
        found.extend(re.findall(pattern, remaining, flags=re.IGNORECASE))
    return list(dict.fromkeys(found))
