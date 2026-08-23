from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import LLMResponse
from skiller.domain.agent.llm.port import LLMPort
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.infrastructure.llm.codex.codex_api import (
    CODEX_AUTH_USER_AGENT,
    CODEX_BASE_URL,
    CODEX_TOKEN_EXPIRY_SKEW_SECONDS,
    CODEX_TOKEN_URL,
    _load_openai_client_class,
    codex_headers,
)
from skiller.infrastructure.llm.codex.codex_credentials_datasource import (
    CodexCredentials,
    CodexCredentialsDatasource,
    CodexCredentialsError,
)
from skiller.infrastructure.llm.codex.codex_mapper import CodexMapper
from skiller.infrastructure.llm.codex.codex_model_capabilities import CodexResponsesProtocol
from skiller.infrastructure.llm.codex.codex_response_model import CodexResponseModel
from skiller.infrastructure.llm.codex.codex_turn_session import (
    CODEX_TURN_STATE_HEADER,
    CodexTurnSession,
    CodexTurnSessionManager,
)
from skiller.infrastructure.llm.codex.collect_codex_response import (
    CollectCodexResponse,
    CollectCodexResponseError,
)
from skiller.infrastructure.llm.codex.responses_mapper import ResponsesMapper
from skiller.infrastructure.llm.logger.request_logger import LLMRequestLogger


@dataclass(frozen=True)
class _CodexToken:
    access_token: str
    account_id: str | None


class _CodexAuthenticationError(ValueError):
    def __init__(self, message: str, *, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class ResponsesLLMPort(LLMPort[CodexLLMRequest]):
    def __init__(
        self,
        *,
        credentials_file: str,
        timeout_seconds: float,
        credentials_datasource: CodexCredentialsDatasource,
        request_logger: LLMRequestLogger,
        request_mapper: CodexMapper,
        response_mapper: ResponsesMapper,
        collector: CollectCodexResponse,
        turn_session_manager: CodexTurnSessionManager,
    ) -> None:
        self.credentials_file = credentials_file
        self.timeout_seconds = timeout_seconds
        self.credentials_datasource = credentials_datasource
        self.request_logger = request_logger
        self.request_mapper = request_mapper
        self.response_mapper = response_mapper
        self.collector = collector
        self.turn_session_manager = turn_session_manager

    def generate(self, request: CodexLLMRequest) -> LLMResponse:
        capabilities = self.request_mapper.capabilities(request)
        turn_session = self.turn_session_manager.resolve(request)
        kwargs = self.request_mapper.to_kwargs(
            request,
            capabilities=capabilities,
            turn_session=turn_session,
        )
        kwargs["stream"] = True
        log_file = request.log_request_file
        capture_stream = request.log_streaming and log_file is not None
        if log_file is not None:
            self.request_logger.log_request(
                request=kwargs,
                file=Path(log_file).expanduser(),
                overwrite=request.log_override_file,
            )

        try:
            token = self._get_token()
            client = self._build_client(token)
            response_model = self._collect_response(
                client,
                kwargs=kwargs,
                protocol=capabilities.protocol,
                turn_session=turn_session,
                log_streaming=capture_stream,
            )
        except _CodexAuthenticationError as exc:
            return self._request_error(
                request=request,
                turn_session=turn_session,
                log_file=log_file,
                error=str(exc),
                error_code=exc.error_code,
            )
        except CollectCodexResponseError as exc:
            self.turn_session_manager.finish(turn_session)
            error = f"Codex stream failed: {exc}"
            if log_file is not None:
                self.request_logger.log_response(
                    response={"stream": exc.stream, "stream_error": error}
                )
            return LLMResponse(
                model=request.model,
                finish_type=LLMFinishType.ERROR_STREAM,
                error=error,
                error_code="stream_failed",
            )
        except Exception as exc:  # noqa: BLE001
            return self._request_error(
                request=request,
                turn_session=turn_session,
                log_file=log_file,
                error=f"Codex request failed: {exc}",
                error_code="request_failed",
            )

        if log_file is not None:
            self.request_logger.log_response(response=response_model)
        if capabilities.protocol == CodexResponsesProtocol.LITE:
            output_items = tuple(response_model.response.output)
            turn_session.record_output_items(output_items)
        response = self.response_mapper.to_response(response_model, request=request)
        if response.finish_type != LLMFinishType.TOOL_CALLS:
            self.turn_session_manager.finish(turn_session)
        return response

    def _collect_response(
        self,
        client: object,
        *,
        kwargs: dict[str, object],
        protocol: CodexResponsesProtocol,
        turn_session: CodexTurnSession,
        log_streaming: bool,
    ) -> CodexResponseModel:
        if protocol == CodexResponsesProtocol.GENERIC:
            events = client.responses.create(**kwargs)
            return self.collector.collect(events, log_streaming=log_streaming)

        response_context = client.responses.with_streaming_response.create(**kwargs)
        with response_context as raw_response:
            headers = getattr(raw_response, "headers", {})
            turn_state = headers.get(CODEX_TURN_STATE_HEADER)
            if isinstance(turn_state, str):
                turn_session.record_turn_state(turn_state)
            return self.collector.collect(
                raw_response.parse(),
                log_streaming=log_streaming,
            )

    def _request_error(
        self,
        *,
        request: CodexLLMRequest,
        turn_session: CodexTurnSession,
        log_file: str | None,
        error: str,
        error_code: str,
    ) -> LLMResponse:
        self.turn_session_manager.finish(turn_session)
        if log_file is not None:
            self.request_logger.log_error(error=error)
        return LLMResponse(
            model=request.model,
            finish_type=LLMFinishType.ERROR_REQUEST_FAILED,
            error=error,
            error_code=error_code,
        )

    def _get_token(self) -> _CodexToken:
        try:
            credentials = self.credentials_datasource.load(self.credentials_file)
        except (CodexCredentialsError, OSError, json.JSONDecodeError) as exc:
            raise _CodexAuthenticationError(
                f"Codex credentials failed: {exc}",
                error_code="credentials_error",
            ) from exc

        expires_at = int(time.time()) + CODEX_TOKEN_EXPIRY_SKEW_SECONDS
        if credentials.expires_at > expires_at:
            return _CodexToken(
                access_token=credentials.access_token,
                account_id=credentials.account_id,
            )
        return self._refresh_token(credentials)

    def _build_client(self, token: _CodexToken) -> object:
        client_class = _load_openai_client_class()
        return client_class(
            api_key=token.access_token,
            base_url=CODEX_BASE_URL,
            timeout=self.timeout_seconds,
            default_headers=codex_headers(token.account_id),
        )

    def _refresh_token(self, credentials: CodexCredentials) -> _CodexToken:
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
            raise _CodexAuthenticationError(
                f"Codex token refresh failed: HTTP {exc.code}",
                error_code="token_refresh_failed",
            ) from exc
        except urllib.error.URLError as exc:
            raise _CodexAuthenticationError(
                f"Codex token refresh request failed: {exc.reason}",
                error_code="token_refresh_failed",
            ) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise _CodexAuthenticationError(
                f"Codex token refresh response failed: {exc}",
                error_code="token_refresh_invalid_response",
            ) from exc
        if not isinstance(token_response, dict):
            raise _CodexAuthenticationError(
                "Codex token refresh response must contain a JSON object",
                error_code="token_refresh_invalid_response",
            )
        try:
            refreshed = self.credentials_datasource.refresh(
                self.credentials_file,
                token_response,
            )
        except (CodexCredentialsError, OSError) as exc:
            raise _CodexAuthenticationError(
                f"Codex token refresh failed: {exc}",
                error_code="token_refresh_failed",
            ) from exc
        return _CodexToken(
            access_token=refreshed.access_token,
            account_id=refreshed.account_id,
        )
