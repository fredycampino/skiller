from __future__ import annotations

from collections.abc import Mapping

from skiller.domain.agent.llm_model import LLMRequest, LLMResponse
from skiller.domain.agent.llm_port import LLMPort
from skiller.infrastructure.llm.openai_responses_mapper import (
    OpenAIResponsesStreamResult,
    to_openai_responses_kwargs,
    to_port_llm_response,
)


def _load_openai_client_class() -> type[object]:
    from openai import OpenAI  # type: ignore[import-not-found]

    return OpenAI


class OpenAIResponsesLLM(LLMPort):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        default_headers: Mapping[str, str] | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.default_headers = dict(default_headers or {})
        self.client = self._build_client()

    def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key.strip():
            return LLMResponse(
                ok=False,
                model=request.model,
                error="API key is not configured for the selected model provider",
                error_code="api_key_missing",
            )

        kwargs = to_openai_responses_kwargs(request)
        text_deltas: list[object] = []
        output_items: list[object] = []

        try:
            with self.client.responses.stream(**kwargs) as stream:
                for event in stream:
                    event_type = getattr(event, "type", "")
                    if event_type == "response.output_text.delta":
                        text_deltas.append(getattr(event, "delta", None))
                        continue
                    if event_type == "response.output_item.done":
                        output_items.append(getattr(event, "item", None))
                        continue
                    if event_type == "error":
                        return LLMResponse(
                            ok=False,
                            model=request.model,
                            error="OpenAI Responses stream emitted an error event",
                            error_code="stream_error",
                        )

                response = stream.get_final_response()
        except Exception as exc:  # noqa: BLE001
            return LLMResponse(
                ok=False,
                model=request.model,
                error=f"OpenAI Responses request failed: {exc}",
                error_code="request_failed",
            )

        stream_result = OpenAIResponsesStreamResult(
            response=response,
            text_deltas=tuple(text_deltas),
            output_items=tuple(output_items),
        )
        return to_port_llm_response(stream_result, fallback_model=request.model)

    def _build_client(self) -> object:
        if not self.api_key.strip():
            return None
        client_class = _load_openai_client_class()
        return client_class(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            default_headers=self.default_headers,
        )
