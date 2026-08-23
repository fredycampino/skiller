from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from openai.types.responses import Response
from openai.types.responses.response import IncompleteDetails
from openai.types.responses.response_function_tool_call import ResponseFunctionToolCall
from openai.types.responses.response_output_message import ResponseOutputMessage
from openai.types.responses.response_output_text import ResponseOutputText

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import LLMUserMessage
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.infrastructure.llm.codex import responses_llm_port
from skiller.infrastructure.llm.codex.codex_credentials_datasource import (
    CodexCredentials,
    CodexCredentialsError,
)
from skiller.infrastructure.llm.codex.codex_mapper import CodexMapper
from skiller.infrastructure.llm.codex.codex_model_capabilities import (
    CodexModelCapabilitiesResolver,
)
from skiller.infrastructure.llm.codex.codex_turn_session import CodexTurnSessionManager
from skiller.infrastructure.llm.codex.collect_codex_response import CollectCodexResponse
from skiller.infrastructure.llm.codex.responses_general_mapper import ResponsesGeneralMapper
from skiller.infrastructure.llm.codex.responses_lite_mapper import ResponsesLiteMapper
from skiller.infrastructure.llm.codex.responses_llm_port import ResponsesLLMPort
from skiller.infrastructure.llm.codex.responses_mapper import ResponsesMapper
from skiller.infrastructure.llm.logger.request_logger import LLMRequestLogger
from skiller.infrastructure.llm.mapper.llm_usage_mapper import DefaultLLMUsageMapper

pytestmark = pytest.mark.unit


class _FakeCredentialsDatasource:
    def load(self, credentials_file: str) -> CodexCredentials:
        _ = credentials_file
        return CodexCredentials(
            access_token="access-token",
            auth_mode="chatgpt",
            refresh_token="refresh-token",
            client_id="client-id",
            created_at=1,
            expires_at=9_999_999_999,
            expires_in=3_600,
            id_token="id-token",
            redirect_uri="http://localhost:1455/auth/callback",
            scope="openid profile email offline_access",
            source="skiller-openai-auth",
            token_type="bearer",
        )

    def refresh(
        self,
        credentials_file: str,
        token_response: dict[str, object],
    ) -> CodexCredentials:
        _ = credentials_file
        _ = token_response
        raise AssertionError("refresh should not run")


class _BrokenCredentialsDatasource(_FakeCredentialsDatasource):
    def load(self, credentials_file: str) -> CodexCredentials:
        _ = credentials_file
        raise CodexCredentialsError("missing credentials")


class _FakeLogger(LLMRequestLogger):
    def __init__(self) -> None:
        self.requests: list[object] = []
        self.responses: list[object] = []
        self.errors: list[str] = []

    def log_request(
        self,
        *,
        request: object,
        file: Path,
        overwrite: bool | None = None,
    ) -> None:
        _ = file
        _ = overwrite
        self.requests.append(request)

    def log_response(self, *, response: object) -> None:
        self.responses.append(response)

    def log_error(self, *, error: str) -> None:
        self.errors.append(error)


class _FakeRawResponse:
    def __init__(self, events: object, headers: dict[str, str]) -> None:
        self.events = events
        self.headers = headers

    def __enter__(self) -> _FakeRawResponse:
        return self

    def __exit__(self, *args: object) -> None:
        _ = args

    def parse(self) -> object:
        if isinstance(self.events, Exception):
            raise self.events
        return self.events


class _FakeStreamingResponses:
    def __init__(self, responses: _FakeResponses) -> None:
        self.responses = responses

    def create(self, **kwargs: object) -> _FakeRawResponse:
        self.responses.calls.append(kwargs)
        return _FakeRawResponse(self.responses.events, self.responses.headers)


class _FakeResponses:
    def __init__(self, events: object, headers: dict[str, str]) -> None:
        self.events = events
        self.headers = headers
        self.calls: list[dict[str, object]] = []
        self.with_streaming_response = _FakeStreamingResponses(self)

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if isinstance(self.events, Exception):
            raise self.events
        return self.events


class _FakeOpenAI:
    events: object = []
    headers: dict[str, str] = {}
    instances: list[_FakeOpenAI] = []

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.responses = _FakeResponses(self.events, self.headers)
        self.instances.append(self)


def _request(
    *,
    model: str = "gpt-5.5",
    log_request_file: str | None = None,
    log_streaming: bool = False,
) -> CodexLLMRequest:
    return CodexLLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=LLMModelDefinition(model=model, context_window_tokens=1_000, max_output_tokens=None),
        parallel_tool_calls=False,
        session_id="session-1",
        log_request_file=log_request_file,
        log_streaming=log_streaming,
    )


def _response(*, output: list[object]) -> Response:
    return Response.model_construct(
        id="resp_test",
        created_at=0,
        model="gpt-5.6",
        object="response",
        output=output,
        parallel_tool_calls=False,
        tool_choice="auto",
        tools=[],
        status="completed",
    )


def _text_response() -> Response:
    message = ResponseOutputMessage.model_construct(
        id="msg_test",
        content=[ResponseOutputText.model_construct(type="output_text", text="hello")],
        role="assistant",
        status="completed",
        type="message",
    )
    return _response(output=[message])


def _tool_response() -> Response:
    tool_call = ResponseFunctionToolCall.model_construct(
        arguments='{"command":"pwd"}',
        call_id="call_1",
        name="shell",
        type="function_call",
    )
    return _response(output=[tool_call])


def _incomplete_tool_response() -> Response:
    response = _tool_response()
    incomplete_details = IncompleteDetails.model_construct(reason="max_output_tokens")
    return response.model_copy(
        update={
            "status": "incomplete",
            "incomplete_details": incomplete_details,
        }
    )


def _port(
    monkeypatch: pytest.MonkeyPatch,
    *,
    events: object,
    headers: dict[str, str] | None = None,
    credentials_datasource: object | None = None,
    logger: _FakeLogger | None = None,
    turn_session_manager: CodexTurnSessionManager | None = None,
) -> tuple[ResponsesLLMPort, _FakeLogger, CodexTurnSessionManager]:
    _FakeOpenAI.events = events
    _FakeOpenAI.headers = headers or {}
    _FakeOpenAI.instances = []
    monkeypatch.setattr(responses_llm_port, "_load_openai_client_class", lambda: _FakeOpenAI)
    usage_mapper = DefaultLLMUsageMapper()
    mapper = CodexMapper(
        capabilities_resolver=CodexModelCapabilitiesResolver(),
        responses_mapper=ResponsesGeneralMapper(),
        responses_lite_mapper=ResponsesLiteMapper(),
    )
    resolved_logger = logger or _FakeLogger()
    sessions = turn_session_manager or CodexTurnSessionManager()
    port = ResponsesLLMPort(
        credentials_file="/tmp/openai-codex.json",
        timeout_seconds=30,
        credentials_datasource=credentials_datasource or _FakeCredentialsDatasource(),
        request_logger=resolved_logger,
        request_mapper=mapper,
        response_mapper=ResponsesMapper(usage_mapper=usage_mapper),
        collector=CollectCodexResponse(),
        turn_session_manager=sessions,
    )
    return port, resolved_logger, sessions


def test_responses_llm_port_collects_and_maps_generic_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = [SimpleNamespace(type="response.completed", response=_text_response())]
    port, logger, sessions = _port(monkeypatch, events=events, logger=_FakeLogger())

    response = port.generate(
        _request(log_request_file="request.json", log_streaming=True)
    )

    assert response.finish_type == LLMFinishType.STOP
    assert response.content == "hello"
    assert logger.responses[0].stream == tuple(events)
    assert sessions.sessions == {}


def test_responses_llm_port_does_not_log_stream_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = [SimpleNamespace(type="response.completed", response=_text_response())]
    port, logger, _ = _port(monkeypatch, events=events, logger=_FakeLogger())

    response = port.generate(_request(log_request_file="request.json"))

    assert response.finish_type == LLMFinishType.STOP
    assert logger.responses[0].stream == ()


def test_responses_llm_port_maps_minimal_completed_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_item = _text_response().output[0]
    events = [
        SimpleNamespace(type="response.output_item.done", item=output_item),
        SimpleNamespace(
            type="response.completed",
            response={
                "id": "resp_minimal",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                },
            },
        ),
    ]
    port, _, sessions = _port(monkeypatch, events=events)

    response = port.generate(_request())

    assert response.finish_type == LLMFinishType.STOP
    assert response.content == "hello"
    assert response.usage is not None
    assert response.usage.prompt_tokens == 10
    assert response.usage.cache_read_tokens is None
    assert sessions.sessions == {}


def test_responses_llm_port_preserves_lite_state_and_output_for_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = [SimpleNamespace(type="response.completed", response=_tool_response())]
    port, _, sessions = _port(
        monkeypatch,
        events=events,
        headers={"x-codex-turn-state": "opaque-turn-state"},
    )

    response = port.generate(_request(model="gpt-5.6-luna"))

    session = sessions.sessions["session-1"]
    assert response.finish_type == LLMFinishType.TOOL_CALLS
    assert session.turn_state == "opaque-turn-state"
    assert session.response_output_batches[0][0]["type"] == "function_call"


def test_responses_llm_port_closes_incomplete_session_with_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = [
        SimpleNamespace(
            type="response.incomplete",
            response=_incomplete_tool_response(),
        )
    ]
    port, _, sessions = _port(monkeypatch, events=events)

    response = port.generate(_request())

    assert response.finish_type == LLMFinishType.INVALID_RESPONSE_LENGTH
    assert response.has_tool_calls is True
    assert sessions.sessions == {}


def test_responses_llm_port_returns_stream_error_with_received_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = SimpleNamespace(type="response.output_text.delta", delta="partial")
    port, logger, sessions = _port(monkeypatch, events=[event], logger=_FakeLogger())

    response = port.generate(
        _request(log_request_file="request.json", log_streaming=True)
    )

    assert response.finish_type == LLMFinishType.ERROR_STREAM
    assert response.error_code == "stream_failed"
    assert logger.responses[0]["stream"] == (event,)
    assert sessions.sessions == {}


def test_responses_llm_port_returns_request_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port, _, sessions = _port(monkeypatch, events=RuntimeError("boom"))

    response = port.generate(_request())

    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert response.error_code == "request_failed"
    assert sessions.sessions == {}


def test_responses_llm_port_returns_credentials_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port, _, sessions = _port(
        monkeypatch,
        events=[],
        credentials_datasource=_BrokenCredentialsDatasource(),
    )

    response = port.generate(_request())

    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert response.error_code == "credentials_error"
    assert sessions.sessions == {}
