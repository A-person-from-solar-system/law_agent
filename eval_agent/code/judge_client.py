import json
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List

from .config import EvalConfig


class JudgeError(RuntimeError):
    pass


class JudgeClient:
    def __init__(self, config: EvalConfig) -> None:
        self.config = config

    @property
    def enabled(self) -> bool:
        return self.config.judge_enabled

    def evaluate(self, system_prompt: str, user_payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            raise JudgeError("Judge model is not configured")
        body = {
            "model": self.config.judge_model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                },
            ],
        }
        request = urllib.request.Request(
            self._endpoint(),
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.judge_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.config.judge_timeout_seconds
            ) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise JudgeError(f"Judge HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise JudgeError(f"Judge request failed: {exc}") from exc

        content = self._content(data)
        return self._parse_json_object(content)

    def _endpoint(self) -> str:
        if self.config.judge_base_url.endswith("/chat/completions"):
            return self.config.judge_base_url
        return self.config.judge_base_url + "/chat/completions"

    @staticmethod
    def _content(data: Dict[str, Any]) -> str:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise JudgeError("Judge response has no choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise JudgeError("Judge response has no text content")
        return content

    @staticmethod
    def _parse_json_object(content: str) -> Dict[str, Any]:
        text = content.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
        if fenced:
            text = fenced.group(1)
        else:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                text = text[start : end + 1]
        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            raise JudgeError(f"Judge did not return valid JSON: {content[:500]}") from exc
        if not isinstance(result, dict):
            raise JudgeError("Judge JSON must be an object")
        return result


def string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
