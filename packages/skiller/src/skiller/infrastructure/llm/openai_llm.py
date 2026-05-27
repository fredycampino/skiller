from __future__ import annotations

from skiller.domain.agent.llm_model import LLMRequest, LLMResponse
from skiller.domain.agent.llm_port import LLMPort
from skiller.infrastructure.llm.openai_mapper import (
    to_openai_kwargs,
    to_port_llm_response,
)


def _load_openai_client_class() -> type[object]:
    from openai import OpenAI  # type: ignore[import-not-found]

    return OpenAI


class OpenAILLM(LLMPort):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.client = self._build_client()

    def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key.strip():
            return LLMResponse(
                ok=False,
                error="API key is not configured for the selected model provider",
                error_code="api_key_missing",
            )

        kwargs = to_openai_kwargs(request)
        kwargs["extra_body"] = {"reasoning_split": True}

        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            return LLMResponse(
                ok=False,
                error=f"OpenAI request failed: {exc}",
                error_code="request_failed",
            )

        return to_port_llm_response(response, fallback_model=request.model)

    def _build_client(self) -> object:
        if not self.api_key.strip():
            return None
        client_class = _load_openai_client_class()
        return client_class(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout_seconds,
        )
