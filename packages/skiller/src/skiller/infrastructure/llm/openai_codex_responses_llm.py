from __future__ import annotations

from skiller.domain.agent.llm_model import LLMRequest, LLMResponse
from skiller.domain.agent.llm_port import LLMPort
from skiller.infrastructure.llm.openai_codex_credentials import (
    OpenAICodexCredentialsLoader,
)
from skiller.infrastructure.llm.openai_responses_mapper import (
    OpenAIResponsesStreamResult,
    to_openai_responses_kwargs,
    to_port_llm_response,
)

CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
CODEX_USER_AGENT = "codex_cli_rs/0.0.0 (Skiller)"
CODEX_ORIGINATOR = "codex_cli_rs"


def _load_openai_client_class() -> type[object]:
    from openai import OpenAI  # type: ignore[import-not-found]

    return OpenAI


class OpenAICodexResponsesLLM(LLMPort):
    def __init__(
        self,
        *,
        credentials_file: str,
        timeout_seconds: float,
        credentials_loader: OpenAICodexCredentialsLoader | None = None,
    ) -> None:
        self.credentials_file = credentials_file
        self.timeout_seconds = timeout_seconds
        self.credentials_loader = credentials_loader or OpenAICodexCredentialsLoader()
        self.client = self._build_client()

    def generate(self, request: LLMRequest) -> LLMResponse:
        kwargs = to_openai_responses_kwargs(request)
        response: object | None = None
        text_deltas: list[object] = []
        output_items: list[object] = []

        try:
            with self.client.responses.stream(**kwargs) as stream:
                for event in stream:
                    event_type = getattr(event, "type", "")
                    if event_type == "response.output_text.delta":
                        text_deltas.append(getattr(event, "delta", None))
                        continue
                    if event_type == "response.completed":
                        response = getattr(event, "response", None)
                        continue
                    if event_type == "response.output_item.done":
                        output_items.append(getattr(event, "item", None))
                        continue
                    if event_type == "error":
                        return LLMResponse(
                            ok=False,
                            error="OpenAI Codex stream emitted an error event",
                            error_code="stream_error",
                        )

                if response is None:
                    response = stream.get_final_response()
        except Exception as exc:  # noqa: BLE001
            if text_deltas or output_items:
                stream_result = OpenAIResponsesStreamResult(
                    response=response,
                    text_deltas=tuple(text_deltas),
                    output_items=tuple(output_items),
                )
                return to_port_llm_response(stream_result, fallback_model=request.model)
            return LLMResponse(
                ok=False,
                error=f"OpenAI Codex request failed: {exc}",
                error_code="request_failed",
            )

        stream_result = OpenAIResponsesStreamResult(
            response=response,
            text_deltas=tuple(text_deltas),
            output_items=tuple(output_items),
        )
        return to_port_llm_response(stream_result, fallback_model=request.model)

    def _build_client(self) -> object:
        credentials = self.credentials_loader.load(self.credentials_file)
        client_class = _load_openai_client_class()
        return client_class(
            api_key=credentials.access_token,
            base_url=CODEX_BASE_URL,
            timeout=self.timeout_seconds,
            default_headers=_codex_headers(credentials.account_id),
        )


def _codex_headers(account_id: str | None) -> dict[str, str]:
    headers = {
        "User-Agent": CODEX_USER_AGENT,
        "originator": CODEX_ORIGINATOR,
    }
    if account_id is not None:
        headers["ChatGPT-Account-ID"] = account_id
    return headers
