from __future__ import annotations

from types import SimpleNamespace

import pytest
from openai.types.responses import Response
from openai.types.responses.response_function_tool_call import ResponseFunctionToolCall

from skiller.infrastructure.llm.codex.collect_codex_response import (
    CollectCodexResponse,
    CollectCodexResponseError,
)

pytestmark = pytest.mark.unit


def _event(event_type: str, **fields: object) -> SimpleNamespace:
    return SimpleNamespace(type=event_type, **fields)


def _response() -> Response:
    return Response.model_construct(
        id="resp_test",
        created_at=0,
        model="gpt-5.6",
        object="response",
        output=[],
        parallel_tool_calls=False,
        tool_choice="auto",
        tools=[],
    )


def _tool_call() -> ResponseFunctionToolCall:
    return ResponseFunctionToolCall.model_construct(
        arguments='{"command":"pwd"}',
        call_id="call_1",
        name="shell",
        type="function_call",
    )


def test_collect_returns_completed_response_and_received_events() -> None:
    response = _response()
    events = [_event("response.created"), _event("response.completed", response=response)]

    result = CollectCodexResponse().collect(events, log_streaming=True)

    assert result.response.status == "completed"
    assert result.stream == tuple(events)


def test_collect_reconstructs_response_output_from_completed_output_items() -> None:
    response = _response()
    tool_call = _tool_call()
    events = [
        _event("response.output_text.delta", delta="hello"),
        _event("response.output_item.done", item=tool_call),
        _event("response.completed", response=response),
    ]

    result = CollectCodexResponse().collect(events, log_streaming=True)

    assert result.response.output == [tool_call]
    assert result.stream == tuple(events)


def test_collect_parses_output_item_done_mapping() -> None:
    response = _response()
    item = {
        "type": "function_call",
        "call_id": "call_1",
        "name": "shell",
        "arguments": '{"command":"pwd"}',
    }

    result = CollectCodexResponse().collect(
        [
            _event("response.output_item.done", item=item),
            _event("response.completed", response=response),
        ],
        log_streaming=True,
    )

    assert isinstance(result.response.output[0], ResponseFunctionToolCall)


def test_collect_accepts_completed_response_without_output_events() -> None:
    response = _response()

    result = CollectCodexResponse().collect([_event("response.completed", response=response)])

    assert result.response.status == "completed"


def test_collect_reconstructs_minimal_completed_response() -> None:
    tool_call = _tool_call()
    events = [
        _event("response.output_item.done", item=tool_call),
        _event("response.completed", response={"id": "resp_minimal"}),
    ]

    result = CollectCodexResponse().collect(events)

    assert result.response.id == "resp_minimal"
    assert result.response.status == "completed"
    assert result.response.output == [tool_call]


def test_collect_uses_terminal_event_as_authoritative_status() -> None:
    response = _response().model_copy(update={"status": "failed"})

    result = CollectCodexResponse().collect(
        [_event("response.completed", response=response)]
    )

    assert result.response.status == "completed"


def test_collect_returns_incomplete_terminal_response() -> None:
    response = _response()

    result = CollectCodexResponse().collect([_event("response.incomplete", response=response)])

    assert result.response.status == "incomplete"


def test_collect_returns_failed_terminal_response() -> None:
    response = _response()

    result = CollectCodexResponse().collect([_event("response.failed", response=response)])

    assert result.response.status == "failed"


def test_collect_preserves_unknown_event_before_terminal_response() -> None:
    response = _response()
    unknown_event = _event("response.future_event", payload={"value": 1})

    result = CollectCodexResponse().collect(
        [unknown_event, _event("response.completed", response=response)],
        log_streaming=True,
    )

    assert result.stream[0] is unknown_event


def test_collect_keeps_terminal_output_when_no_output_item_done_event_arrives() -> None:
    tool_call = _tool_call()
    response = _response().model_copy(update={"output": [tool_call]})

    result = CollectCodexResponse().collect([_event("response.completed", response=response)])

    assert result.response.output == [tool_call]


def test_collect_returns_when_terminal_event_arrives_without_waiting_for_stream_end() -> None:
    response = _response()

    def stream() -> object:
        yield _event("response.completed", response=response)
        raise AssertionError("collector must not read after the terminal event")

    result = CollectCodexResponse().collect(stream(), log_streaming=True)

    assert result.response.status == "completed"


def test_collect_rejects_empty_stream() -> None:
    with pytest.raises(CollectCodexResponseError, match="without a terminal response") as exc:
        CollectCodexResponse().collect([])

    assert exc.value.stream == ()


def test_collect_rejects_iteration_error_and_preserves_received_events() -> None:
    event = _event("response.output_text.delta", delta="partial")

    def stream() -> object:
        yield event
        raise RuntimeError("connection lost")

    with pytest.raises(CollectCodexResponseError, match="iteration failed") as exc:
        CollectCodexResponse().collect(stream(), log_streaming=True)

    assert exc.value.stream == (event,)


def test_collect_does_not_retain_events_when_stream_logging_is_disabled() -> None:
    response = _response()
    events = [_event("response.created"), _event("response.completed", response=response)]

    result = CollectCodexResponse().collect(events)

    assert result.response.status == "completed"
    assert result.stream == ()


def test_collect_rejects_error_event_and_preserves_received_events() -> None:
    created = _event("response.created")
    error = _event("error")

    with pytest.raises(CollectCodexResponseError, match="emitted an error event") as exc:
        CollectCodexResponse().collect([created, error], log_streaming=True)

    assert exc.value.stream == (created, error)


def test_collect_rejects_event_without_string_type() -> None:
    event = SimpleNamespace(type=None)

    with pytest.raises(CollectCodexResponseError, match="type must be a string") as exc:
        CollectCodexResponse().collect([event], log_streaming=True)

    assert exc.value.stream == (event,)


def test_collect_rejects_terminal_event_without_response() -> None:
    event = _event("response.completed")

    with pytest.raises(CollectCodexResponseError, match="must contain a response object") as exc:
        CollectCodexResponse().collect([event], log_streaming=True)

    assert exc.value.stream == (event,)


def test_collect_rejects_output_item_done_without_item() -> None:
    event = _event("response.output_item.done")

    with pytest.raises(CollectCodexResponseError, match="must contain an output item") as exc:
        CollectCodexResponse().collect([event], log_streaming=True)

    assert exc.value.stream == (event,)
