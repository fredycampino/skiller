from __future__ import annotations

from skiller.domain.agent.llm_model import LLMResponse
from skiller.domain.agent.llm_port import LLMPort
from skiller.domain.agent.llm_request import CodexLLMRequest
from skiller.infrastructure.llm.openai_codex_credentials import (
    OpenAICodexCredentialsLoader,
)
from skiller.infrastructure.llm.openai_responses_mapper import (
    OpenAIResponsesStreamResult,
    to_openai_responses_prompt_payload,
    to_openai_responses_response_format_payload,
    to_openai_responses_tool_payload,
    to_port_llm_response,
)

CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
CODEX_USER_AGENT = "codex_cli_rs/0.0.0 (Skiller)"
CODEX_ORIGINATOR = "codex_cli_rs"


def _load_openai_client_class() -> type[object]:
    from openai import OpenAI  # type: ignore[import-not-found]

    return OpenAI


class OpenAICodexResponsesLLM(LLMPort[CodexLLMRequest]):
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

    def generate(self, request: CodexLLMRequest) -> LLMResponse:
        kwargs = _to_openai_codex_responses_kwargs(request)
        kwargs["stream"] = True
        response: object | None = None
        text_deltas: list[object] = []
        output_items: list[object] = []

        try:
            for event in self.client.responses.create(**kwargs):
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
                        model=request.model,
                        error="OpenAI Codex stream emitted an error event",
                        error_code="stream_error",
                    )
        except Exception as exc:  # noqa: BLE001
            if text_deltas or output_items:
                stream_result = OpenAIResponsesStreamResult(
                    response=response,
                    text_deltas=tuple(text_deltas),
                    output_items=tuple(output_items),
                )
                return to_port_llm_response(
                    stream_result,
                    fallback_model=request.model,
                )
            return LLMResponse(
                ok=False,
                model=request.model,
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


def _to_openai_codex_responses_kwargs(request: CodexLLMRequest) -> dict[str, object]:
    instructions, input_items = to_openai_responses_prompt_payload(request.messages)
    payload: dict[str, object] = {
        "model": request.model.value,
        "instructions": instructions,
        "input": input_items,
        "store": False,
        "tool_choice": "auto",
        "parallel_tool_calls": request.parallel_tool_calls,
    }
    if request.tools:
        payload["tools"] = [to_openai_responses_tool_payload(tool) for tool in request.tools]
    if request.response_format is not None:
        payload["text"] = {
            "format": to_openai_responses_response_format_payload(
                request.response_format,
            )
        }
    return payload


def _codex_headers(account_id: str | None) -> dict[str, str]:
    headers = {
        "User-Agent": CODEX_USER_AGENT,
        "originator": CODEX_ORIGINATOR,
    }
    if account_id is not None:
        headers["ChatGPT-Account-ID"] = account_id
    return headers
