from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from skiller.domain.agent.llm.model import LLMResponse
from skiller.domain.agent.llm.port import LLMPort
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.infrastructure.llm.codex.codex_credentials_datasource import (
    CodexCredentials,
    CodexCredentialsDatasource,
    CodexCredentialsError,
)
from skiller.infrastructure.llm.codex.codex_mapper import (
    CodexStreamResult,
    to_codex_prompt_payload,
    to_codex_response_format_payload,
    to_codex_tool_payload,
    to_port_llm_response,
)

CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
CODEX_TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_USER_AGENT = "codex_cli_rs/0.0.0 (Skiller)"
CODEX_ORIGINATOR = "codex_cli_rs"
CODEX_AUTH_USER_AGENT = "skiller-openai-auth/0.1"
CODEX_TOKEN_EXPIRY_SKEW_SECONDS = 60


@dataclass(frozen=True)
class CodexError:
    error: str
    error_code: str


@dataclass(frozen=True)
class CodexToken:
    access_token: str
    account_id: str | None


def _load_openai_client_class() -> type[object]:
    from openai import OpenAI  # type: ignore[import-not-found]

    return OpenAI


class CodexLLMPort(LLMPort[CodexLLMRequest]):
    def __init__(
        self,
        *,
        credentials_file: str,
        timeout_seconds: float,
        credentials_datasource: CodexCredentialsDatasource,
    ) -> None:
        self.credentials_file = credentials_file
        self.timeout_seconds = timeout_seconds
        self.credentials_datasource = credentials_datasource

    def generate(self, request: CodexLLMRequest) -> LLMResponse:
        token = self._get_token()
        if isinstance(token, CodexError):
            return LLMResponse(
                ok=False,
                model=request.model,
                error=token.error,
                error_code=token.error_code,
            )

        client = self._build_client(token)
        kwargs = _to_codex_kwargs(request)
        kwargs["stream"] = True
        response: object | None = None
        text_deltas: list[object] = []
        output_items: list[object] = []

        try:
            for event in client.responses.create(**kwargs):
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
                        error="Codex stream emitted an error event",
                        error_code="stream_error",
                    )
        except Exception as exc:  # noqa: BLE001
            if text_deltas or output_items:
                stream_result = CodexStreamResult(
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
                error=f"Codex request failed: {exc}",
                error_code="request_failed",
            )

        stream_result = CodexStreamResult(
            response=response,
            text_deltas=tuple(text_deltas),
            output_items=tuple(output_items),
        )
        return to_port_llm_response(stream_result, fallback_model=request.model)

    def _get_token(self) -> CodexToken | CodexError:
        try:
            credentials = self.credentials_datasource.load(self.credentials_file)
        except (CodexCredentialsError, OSError, json.JSONDecodeError) as exc:
            return CodexError(
                error=f"Codex credentials failed: {exc}",
                error_code="credentials_error",
            )

        expires_at = int(time.time()) + CODEX_TOKEN_EXPIRY_SKEW_SECONDS
        if credentials.expires_at > expires_at:
            return CodexToken(
                access_token=credentials.access_token,
                account_id=credentials.account_id,
            )

        return self._refresh_token(credentials)

    def _build_client(self, token: CodexToken) -> object:
        client_class = _load_openai_client_class()
        return client_class(
            api_key=token.access_token,
            base_url=CODEX_BASE_URL,
            timeout=self.timeout_seconds,
            default_headers=_codex_headers(token.account_id),
        )

    def _refresh_token(
        self,
        credentials: CodexCredentials,
    ) -> CodexToken | CodexError:
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": credentials.refresh_token,
            "client_id": credentials.client_id,
        }
        request = urllib.request.Request(
            CODEX_TOKEN_URL,
            data=urllib.parse.urlencode(payload).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": CODEX_AUTH_USER_AGENT,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                token_response = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return CodexError(
                error=f"Codex token refresh failed: HTTP {exc.code}",
                error_code="token_refresh_failed",
            )
        except urllib.error.URLError as exc:
            return CodexError(
                error=f"Codex token refresh request failed: {exc.reason}",
                error_code="token_refresh_failed",
            )
        except (OSError, json.JSONDecodeError) as exc:
            return CodexError(
                error=f"Codex token refresh response failed: {exc}",
                error_code="token_refresh_invalid_response",
            )
        if not isinstance(token_response, dict):
            return CodexError(
                error="Codex token refresh response must contain a JSON object",
                error_code="token_refresh_invalid_response",
            )

        try:
            refreshed = self.credentials_datasource.refresh(
                self.credentials_file,
                token_response,
            )
        except (CodexCredentialsError, OSError) as exc:
            return CodexError(
                error=f"Codex token refresh failed: {exc}",
                error_code="token_refresh_failed",
            )
        return CodexToken(
            access_token=refreshed.access_token,
            account_id=refreshed.account_id,
        )


def _to_codex_kwargs(request: CodexLLMRequest) -> dict[str, object]:
    instructions, input_items = to_codex_prompt_payload(request.messages)
    payload: dict[str, object] = {
        "model": request.model.value,
        "instructions": instructions,
        "input": input_items,
        "store": False,
        "tool_choice": "auto",
        "parallel_tool_calls": request.parallel_tool_calls,
    }
    if request.tools:
        payload["tools"] = [to_codex_tool_payload(tool) for tool in request.tools]
    if request.response_format is not None:
        payload["text"] = {
            "format": to_codex_response_format_payload(
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
