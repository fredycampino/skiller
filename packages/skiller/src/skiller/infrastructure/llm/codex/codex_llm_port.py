from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from skiller.domain.agent.llm.model import LLMResponse
from skiller.domain.agent.llm.port import LLMPort
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.infrastructure.llm.codex.codex_credentials_datasource import (
    CodexCredentials,
    CodexCredentialsDatasource,
    CodexCredentialsError,
)
from skiller.infrastructure.llm.codex.codex_mapper import (
    CodexMapper,
    CodexStreamResult,
)
from skiller.infrastructure.llm.codex.codex_model_capabilities import (
    CodexResponsesProtocol,
)
from skiller.infrastructure.llm.codex.codex_turn_session import (
    CODEX_TURN_STATE_HEADER,
    CodexTurnSession,
    CodexTurnSessionManager,
)
from skiller.infrastructure.llm.logger.request_logger import LLMRequestLogger

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


@dataclass
class _CodexStreamAccumulator:
    response: object | None = None
    text_deltas: list[object] = field(default_factory=list)
    output_items: list[object] = field(default_factory=list)

    @property
    def has_partial_response(self) -> bool:
        return bool(self.text_deltas or self.output_items)

    def read(self, events: Iterable[object]) -> CodexError | None:
        for event in events:
            event_type = getattr(event, "type", "")
            if event_type == "response.output_text.delta":
                self.text_deltas.append(getattr(event, "delta", None))
                continue
            if event_type == "response.completed":
                self.response = getattr(event, "response", None)
                continue
            if event_type == "response.output_item.done":
                self.output_items.append(getattr(event, "item", None))
                continue
            if event_type == "error":
                return CodexError(
                    error="Codex stream emitted an error event",
                    error_code="stream_error",
                )
        return None

    def result(self) -> CodexStreamResult:
        return CodexStreamResult(
            response=self.response,
            text_deltas=tuple(self.text_deltas),
            output_items=tuple(self.output_items),
        )


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
        request_logger: LLMRequestLogger,
        mapper: CodexMapper,
        turn_session_manager: CodexTurnSessionManager,
    ) -> None:
        self.credentials_file = credentials_file
        self.timeout_seconds = timeout_seconds
        self.credentials_datasource = credentials_datasource
        self.request_logger = request_logger
        self.mapper = mapper
        self.turn_session_manager = turn_session_manager

    def generate(self, request: CodexLLMRequest) -> LLMResponse:
        capabilities = self.mapper.capabilities(request)
        turn_session = self.turn_session_manager.resolve(request)
        kwargs = self.mapper.to_kwargs(
            request,
            capabilities=capabilities,
            turn_session=turn_session,
        )
        kwargs["stream"] = True
        log_file = request.log_request_file
        if log_file is not None:
            self.request_logger.log_request(
                request=kwargs,
                file=Path(log_file).expanduser(),
                overwrite=request.log_override_file,
            )

        token = self._get_token()
        if isinstance(token, CodexError):
            self.turn_session_manager.finish(turn_session)
            if log_file is not None:
                self.request_logger.log_error(error=token.error)
            return LLMResponse(
                ok=False,
                model=request.model,
                error=token.error,
                error_code=token.error_code,
            )

        client = self._build_client(token)
        stream = _CodexStreamAccumulator()

        try:
            stream_error = self._read_response_stream(
                client,
                kwargs=kwargs,
                protocol=capabilities.protocol,
                turn_session=turn_session,
                stream=stream,
            )
        except Exception as exc:  # noqa: BLE001
            stream_result = stream.result()
            self._record_lite_response(
                protocol=capabilities.protocol,
                turn_session=turn_session,
                stream_result=stream_result,
            )
            if log_file is not None:
                if stream.response is not None:
                    self.request_logger.log_response(response=stream.response)
                else:
                    self.request_logger.log_error(error=f"Codex request failed: {exc}")
            if stream.has_partial_response:
                response = self.mapper.to_response(
                    stream_result,
                    request=request,
                )
                self._finish_turn_without_tool_calls(
                    response=response,
                    turn_session=turn_session,
                )
                return response
            self.turn_session_manager.finish(turn_session)
            return LLMResponse(
                ok=False,
                model=request.model,
                error=f"Codex request failed: {exc}",
                error_code="request_failed",
            )

        if stream_error is not None:
            self.turn_session_manager.finish(turn_session)
            if log_file is not None:
                self.request_logger.log_error(error=stream_error.error)
            return LLMResponse(
                ok=False,
                model=request.model,
                error=stream_error.error,
                error_code=stream_error.error_code,
            )

        if log_file is not None:
            if stream.response is not None:
                self.request_logger.log_response(response=stream.response)
            else:
                self.request_logger.log_error(
                    error="Codex stream completed without response.completed"
                )

        stream_result = stream.result()
        self._record_lite_response(
            protocol=capabilities.protocol,
            turn_session=turn_session,
            stream_result=stream_result,
        )
        response = self.mapper.to_response(stream_result, request=request)
        self._finish_turn_without_tool_calls(
            response=response,
            turn_session=turn_session,
        )
        return response

    def _read_response_stream(
        self,
        client: object,
        *,
        kwargs: dict[str, object],
        protocol: CodexResponsesProtocol,
        turn_session: CodexTurnSession,
        stream: _CodexStreamAccumulator,
    ) -> CodexError | None:
        if protocol == CodexResponsesProtocol.GENERIC:
            events = client.responses.create(**kwargs)
            return stream.read(events)

        response_context = client.responses.with_streaming_response.create(**kwargs)
        with response_context as raw_response:
            headers = getattr(raw_response, "headers", {})
            turn_state = headers.get(CODEX_TURN_STATE_HEADER)
            if isinstance(turn_state, str):
                turn_session.record_turn_state(turn_state)
            events = raw_response.parse()
            return stream.read(events)

    def _record_lite_response(
        self,
        *,
        protocol: CodexResponsesProtocol,
        turn_session: CodexTurnSession,
        stream_result: CodexStreamResult,
    ) -> None:
        if protocol != CodexResponsesProtocol.LITE:
            return

        response_output = _read_response_output(stream_result.response)
        output_items = response_output or stream_result.output_items
        turn_session.record_output_items(output_items)

    def _finish_turn_without_tool_calls(
        self,
        *,
        response: LLMResponse,
        turn_session: CodexTurnSession,
    ) -> None:
        if not response.has_tool_calls:
            self.turn_session_manager.finish(turn_session)

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


def _codex_headers(account_id: str | None) -> dict[str, str]:
    headers = {
        "User-Agent": CODEX_USER_AGENT,
        "originator": CODEX_ORIGINATOR,
    }
    if account_id is not None:
        headers["ChatGPT-Account-ID"] = account_id
    return headers


def _read_response_output(response: object | None) -> tuple[object, ...]:
    if response is None:
        return ()
    output = getattr(response, "output", None)
    if output is None and isinstance(response, Mapping):
        output = response.get("output")
    if not isinstance(output, list):
        return ()
    return tuple(output)
