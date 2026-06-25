from __future__ import annotations

from typing import Generic, TypeVar

from skiller.domain.agent.llm.model import LLMResponse
from skiller.domain.agent.llm.port import LLMPort
from skiller.domain.agent.llm.request import LLMRequest
from skiller.infrastructure.llm.openai.openai_mapper import (
    OpenAIMapper,
)

RequestT = TypeVar("RequestT", bound=LLMRequest)


def _load_openai_client_class() -> type[object]:
    from openai import OpenAI  # type: ignore[import-not-found]

    return OpenAI


class OpenAILLMPort(LLMPort[RequestT], Generic[RequestT]):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        mapper: OpenAIMapper[RequestT],
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.mapper = mapper
        self.client = self._build_client()

    def generate(self, request: RequestT) -> LLMResponse:
        if not self.api_key.strip():
            return LLMResponse(
                ok=False,
                model=request.model,
                error="API key is not configured for the selected model provider",
                error_code="api_key_missing",
            )

        kwargs = self.mapper.to_kwargs(request)

        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            return LLMResponse(
                ok=False,
                model=request.model,
                error=f"OpenAI request failed: {exc}",
                error_code="request_failed",
            )

        return self.mapper.to_response(response, fallback_model=request.model)

    def _build_client(self) -> object:
        if not self.api_key.strip():
            return None
        client_class = _load_openai_client_class()
        return client_class(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout_seconds,
        )
