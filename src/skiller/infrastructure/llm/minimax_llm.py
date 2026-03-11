from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class MinimaxLLM:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.minimax.io/v1",
        model: str = "MiniMax-M2.5",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        messages: list[dict[str, str]],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.api_key.strip():
            return {"ok": False, "error": "MiniMax API key is not configured"}

        model = self._resolve_model(config)
        payload = {
            "model": model,
            "messages": messages,
            "reasoning_split": True,
        }

        try:
            response = self._post_json("/chat/completions", payload)
        except HTTPError as exc:
            return {"ok": False, "error": self._extract_http_error(exc)}
        except (URLError, TimeoutError, ValueError) as exc:
            return {"ok": False, "error": f"MiniMax request failed: {exc}"}

        return self._parse_response(response, model=model)

    def _resolve_model(self, config: dict[str, Any] | None) -> str:
        if config is None:
            return self.model

        raw_model = config.get("model")
        if isinstance(raw_model, str) and raw_model.strip():
            return raw_model.strip()
        return self.model

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers={
                "content-type": "application/json",
                "authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            raw_payload = response.read().decode("utf-8")

        parsed = json.loads(raw_payload)
        if not isinstance(parsed, dict):
            raise ValueError("MiniMax returned invalid JSON payload")
        return parsed

    def _parse_response(self, payload: dict[str, Any], *, model: str) -> dict[str, Any]:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return {"ok": False, "error": "MiniMax response missing choices"}

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            return {"ok": False, "error": "MiniMax response contains invalid choice payload"}

        message = first_choice.get("message")
        if not isinstance(message, dict):
            return {"ok": False, "error": "MiniMax response missing message payload"}

        content = message.get("content")
        if not isinstance(content, str):
            return {"ok": False, "error": "MiniMax response missing text content"}

        response_model = payload.get("model")
        return {
            "ok": True,
            "content": content,
            "model": str(response_model) if isinstance(response_model, str) else model,
        }

    def _extract_http_error(self, error: HTTPError) -> str:
        try:
            raw_payload = error.read().decode("utf-8")
            parsed = json.loads(raw_payload)
        except Exception:  # noqa: BLE001
            return f"MiniMax request failed with HTTP {error.code}"

        if not isinstance(parsed, dict):
            return f"MiniMax request failed with HTTP {error.code}"

        raw_error = parsed.get("error")
        if isinstance(raw_error, dict):
            message = raw_error.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()

        message = parsed.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

        return f"MiniMax request failed with HTTP {error.code}"
