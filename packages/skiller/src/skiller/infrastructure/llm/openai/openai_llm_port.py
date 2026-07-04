from __future__ import annotations

from typing import Generic, TypeVar

from skiller.domain.agent.llm.model import LLMResponse
from skiller.domain.agent.llm.port import LLMPort
from skiller.domain.agent.llm.request import LLMRequest
from skiller.infrastructure.llm.logger.request_logger import LLMRequestLogger
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
        request_logger: LLMRequestLogger,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.mapper = mapper
        self.request_logger = request_logger
        self.client = self._build_client()

    def generate(self, request: RequestT) -> LLMResponse:
        kwargs = self.mapper.to_kwargs(request)
        if request.log_request:
            self.request_logger.log_request(request=kwargs)

        if not self.api_key.strip():
            response = LLMResponse(
                ok=False,
                model=request.model,
                error="API key is not configured for the selected model provider",
                error_code="api_key_missing",
            )
            if request.log_request and response.error is not None:
                self.request_logger.log_error(error=response.error)
            return response

        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            error = f"OpenAI request failed: {exc}"
            if request.log_request:
                self.request_logger.log_error(error=error)
            return LLMResponse(
                ok=False,
                model=request.model,
                error=error,
                error_code="request_failed",
            )

        if request.log_request:
            self.request_logger.log_response(response=response)

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
