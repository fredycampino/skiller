from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from skiller.domain.agent.llm_model import LLMRequest, LLMResponse
from skiller.infrastructure.llm.openai_mapper import (
    to_openai_kwargs,
    to_port_llm_response,
)


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

    def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key.strip():
            return LLMResponse(
                ok=False,
                error="MiniMax API key is not configured",
                error_code="api_key_missing",
            )

        payload = to_openai_kwargs(request, default_model=self.model)
        # Keep MiniMax reasoning out of message.content so agent context, step output,
        # and TUI transcript stay aligned with the OpenAI-style content we expect.
        payload["reasoning_split"] = True

        try:
            response = self._post_json("/chat/completions", payload)
        except HTTPError as exc:
            return LLMResponse(
                ok=False,
                error=self._extract_http_error(exc),
                error_code=f"http_{exc.code}",
            )
        except (URLError, TimeoutError, ValueError) as exc:
            return LLMResponse(
                ok=False,
                error=f"MiniMax request failed: {exc}",
                error_code="request_failed",
            )

        return to_port_llm_response(response, fallback_model=str(payload["model"]))

    def _post_json(self, path: str, payload: dict[str, object]) -> dict[str, object]:
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
