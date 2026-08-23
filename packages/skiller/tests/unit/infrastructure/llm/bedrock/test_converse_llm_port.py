from __future__ import annotations

from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import LLMUserMessage
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition
from skiller.infrastructure.llm.bedrock import converse_llm_port
from skiller.infrastructure.llm.bedrock.bedrock_mapper import BedrockMapper
from skiller.infrastructure.llm.bedrock.collect_converse_response import CollectConverseResponse
from skiller.infrastructure.llm.bedrock.converse_llm_port import ConverseLLMPort
from skiller.infrastructure.llm.bedrock.converse_mapper import ConverseMapper
from skiller.infrastructure.llm.logger.request_logger import LLMRequestLogger
from skiller.infrastructure.llm.mapper.llm_usage_mapper import DefaultLLMUsageMapper

pytestmark = pytest.mark.unit


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


class _FakeClient:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def converse_stream(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class _FakeSession:
    response: object = {}
    instances: list[_FakeSession] = []

    def __init__(self, *, profile_name: str) -> None:
        self.profile_name = profile_name
        self.runtime_client = _FakeClient(self.response)
        self.instances.append(self)

    def client(self, service_name: str, **kwargs: object) -> _FakeClient:
        _ = service_name
        _ = kwargs
        return self.runtime_client


class _FakeConfig:
    def __init__(self, *, read_timeout: float) -> None:
        self.read_timeout = read_timeout


def _request(
    *,
    log_request_file: str | None = None,
    log_streaming: bool = False,
) -> BedrockLLMRequest:
    return BedrockLLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=LLMModelDefinition(model="test", context_window_tokens=1_000, max_output_tokens=None),
        log_request_file=log_request_file,
        log_streaming=log_streaming,
    )


def _stream() -> list[object]:
    return [
        {"messageStart": {"role": "assistant"}},
        {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "Hello"}}},
        {"contentBlockStop": {"contentBlockIndex": 0}},
        {"messageStop": {"stopReason": "end_turn"}},
        {"metadata": {"usage": {}, "metrics": {"latencyMs": 1}}},
    ]


def _port(
    monkeypatch: pytest.MonkeyPatch, *, response: object, logger: _FakeLogger
) -> ConverseLLMPort:
    _FakeSession.instances = []
    _FakeSession.response = response
    monkeypatch.setattr(converse_llm_port, "_load_boto3_session_class", lambda: _FakeSession)
    monkeypatch.setattr(converse_llm_port, "_load_botocore_config_class", lambda: _FakeConfig)
    usage_mapper = DefaultLLMUsageMapper()
    return ConverseLLMPort(
        profile="bedrock",
        timeout_seconds=30,
        request_logger=logger,
        request_mapper=BedrockMapper(),
        response_mapper=ConverseMapper(usage_mapper=usage_mapper),
        collector=CollectConverseResponse(),
    )


def test_converse_llm_port_collects_and_maps_response(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = _FakeLogger()
    port = _port(monkeypatch, response={"stream": _stream()}, logger=logger)

    response = port.generate(
        _request(log_request_file="request.json", log_streaming=True)
    )

    assert response.finish_type == LLMFinishType.STOP
    assert response.content == "Hello"
    assert _FakeSession.instances[0].runtime_client.calls
    assert logger.responses[0].stream == tuple(_stream())


def test_converse_llm_port_does_not_log_stream_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _FakeLogger()
    port = _port(monkeypatch, response={"stream": _stream()}, logger=logger)

    response = port.generate(_request(log_request_file="request.json"))

    assert response.finish_type == LLMFinishType.STOP
    assert logger.responses[0].stream == ()


def test_converse_llm_port_returns_stream_error_with_received_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _FakeLogger()
    stream = _stream()[:-1]
    port = _port(monkeypatch, response={"stream": stream}, logger=logger)

    response = port.generate(
        _request(log_request_file="request.json", log_streaming=True)
    )

    assert response.finish_type == LLMFinishType.ERROR_STREAM
    assert response.error_code == "stream_failed"
    assert logger.responses == [
        {
            "stream": tuple(stream),
            "stream_error": "Bedrock Converse stream failed: "
            "Bedrock stream ended without metadata event",
        }
    ]


def test_converse_llm_port_returns_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenClient:
        def converse_stream(self, **kwargs: object) -> object:
            _ = kwargs
            raise RuntimeError("boom")

    class _BrokenSession:
        def __init__(self, *, profile_name: str) -> None:
            _ = profile_name

        def client(self, service_name: str, **kwargs: object) -> _BrokenClient:
            _ = service_name
            _ = kwargs
            return _BrokenClient()

    monkeypatch.setattr(converse_llm_port, "_load_boto3_session_class", lambda: _BrokenSession)
    monkeypatch.setattr(converse_llm_port, "_load_botocore_config_class", lambda: _FakeConfig)
    usage_mapper = DefaultLLMUsageMapper()
    port = ConverseLLMPort(
        profile="bedrock",
        timeout_seconds=30,
        request_logger=_FakeLogger(),
        request_mapper=BedrockMapper(),
        response_mapper=ConverseMapper(usage_mapper=usage_mapper),
        collector=CollectConverseResponse(),
    )

    response = port.generate(_request())

    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert response.error_code == "request_failed"


def _http_error(status_code: int) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": "Error", "Message": f"HTTP {status_code}"},
            "ResponseMetadata": {"HTTPStatusCode": status_code},
        },
        "ConverseStream",
    )


def test_converse_llm_port_returns_unauthorized_error_for_http_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = _port(monkeypatch, response=_http_error(401), logger=_FakeLogger())

    response = port.generate(_request())

    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert response.error_code == "unauthorized"


def test_converse_llm_port_returns_forbidden_error_for_http_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = _port(monkeypatch, response=_http_error(403), logger=_FakeLogger())

    response = port.generate(_request())

    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert response.error_code == "forbidden"


def test_converse_llm_port_returns_model_not_available_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = ClientError(
        {
            "Error": {
                "Code": "AccessDeniedException",
                "Message": "anthropic.claude-opus-4-8 is not available for this account.",
            },
            "ResponseMetadata": {"HTTPStatusCode": 403},
        },
        "ConverseStream",
    )
    port = _port(monkeypatch, response=error, logger=_FakeLogger())

    response = port.generate(_request())

    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert response.error_code == "model_not_available"


def test_converse_llm_port_returns_invalid_model_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = ClientError(
        {
            "Error": {
                "Code": "ValidationException",
                "Message": "The provided model identifier is invalid.",
            },
            "ResponseMetadata": {"HTTPStatusCode": 400},
        },
        "ConverseStream",
    )
    port = _port(monkeypatch, response=error, logger=_FakeLogger())

    response = port.generate(_request())

    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert response.error_code == "invalid_model"


def test_converse_llm_port_returns_bad_request_error_for_http_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = _port(monkeypatch, response=_http_error(400), logger=_FakeLogger())

    response = port.generate(_request())

    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert response.error_code == "bad_request"


def test_converse_llm_port_returns_rate_limit_error_for_http_429(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = _port(monkeypatch, response=_http_error(429), logger=_FakeLogger())

    response = port.generate(_request())

    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert response.error_code == "rate_limit"


def test_converse_llm_port_returns_server_error_for_http_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = _port(monkeypatch, response=_http_error(500), logger=_FakeLogger())

    response = port.generate(_request())

    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert response.error_code == "server_error"
