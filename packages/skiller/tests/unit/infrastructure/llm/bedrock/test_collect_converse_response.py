from __future__ import annotations

import pytest

from skiller.infrastructure.llm.bedrock.collect_converse_response import (
    CollectConverseResponse,
    CollectConverseResponseError,
)
from skiller.infrastructure.llm.bedrock.converse_response_model import (
    ConverseMetricsModel,
    ConverseResponseModel,
    ConverseTextContentBlock,
    ConverseToolUseContentBlock,
    ConverseUsageModel,
)

pytestmark = pytest.mark.unit


def _metadata() -> dict[str, object]:
    return {
        "metadata": {
            "usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
            "metrics": {"latencyMs": 20},
        }
    }


def _text_stream() -> list[object]:
    return [
        {"messageStart": {"role": "assistant"}},
        {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "Hello"}}},
        {"contentBlockStop": {"contentBlockIndex": 0}},
        {"messageStop": {"stopReason": "end_turn"}},
        _metadata(),
    ]


def test_collect_reconstructs_single_text_response() -> None:
    stream = _text_stream()

    response = CollectConverseResponse().collect(stream, log_streaming=True)

    assert response.content == (ConverseTextContentBlock(text="Hello"),)


def test_collect_reconstructs_single_delta_tool_use_response() -> None:
    stream = [
        {"messageStart": {"role": "assistant"}},
        {
            "contentBlockStart": {
                "contentBlockIndex": 0,
                "start": {"toolUse": {"toolUseId": "tooluse_1", "name": "shell"}},
            }
        },
        {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"toolUse": {"input": "{}"}}}},
        {"contentBlockStop": {"contentBlockIndex": 0}},
        {"messageStop": {"stopReason": "tool_use"}},
        _metadata(),
    ]

    response = CollectConverseResponse().collect(stream)

    assert response.content == (
        ConverseToolUseContentBlock(tool_use_id="tooluse_1", name="shell", input={}),
    )


def test_collect_reconstructs_multiple_tool_use_responses() -> None:
    stream = [
        {"messageStart": {"role": "assistant"}},
        {
            "contentBlockStart": {
                "contentBlockIndex": 0,
                "start": {"toolUse": {"toolUseId": "tooluse_1", "name": "shell"}},
            }
        },
        {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"toolUse": {"input": "{}"}}}},
        {"contentBlockStop": {"contentBlockIndex": 0}},
        {
            "contentBlockStart": {
                "contentBlockIndex": 1,
                "start": {"toolUse": {"toolUseId": "tooluse_2", "name": "clock"}},
            }
        },
        {"contentBlockDelta": {"contentBlockIndex": 1, "delta": {"toolUse": {"input": "{}"}}}},
        {"contentBlockStop": {"contentBlockIndex": 1}},
        {"messageStop": {"stopReason": "tool_use"}},
        _metadata(),
    ]

    response = CollectConverseResponse().collect(stream)

    assert response.content == (
        ConverseToolUseContentBlock(tool_use_id="tooluse_1", name="shell", input={}),
        ConverseToolUseContentBlock(tool_use_id="tooluse_2", name="clock", input={}),
    )


def test_collect_preserves_text_and_tool_use_order() -> None:
    stream = [
        {"messageStart": {"role": "assistant"}},
        {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "Running: "}}},
        {"contentBlockStop": {"contentBlockIndex": 0}},
        {
            "contentBlockStart": {
                "contentBlockIndex": 1,
                "start": {"toolUse": {"toolUseId": "tooluse_1", "name": "shell"}},
            }
        },
        {"contentBlockDelta": {"contentBlockIndex": 1, "delta": {"toolUse": {"input": "{}"}}}},
        {"contentBlockStop": {"contentBlockIndex": 1}},
        {"messageStop": {"stopReason": "tool_use"}},
        _metadata(),
    ]

    response = CollectConverseResponse().collect(stream)

    assert response.content == (
        ConverseTextContentBlock(text="Running: "),
        ConverseToolUseContentBlock(tool_use_id="tooluse_1", name="shell", input={}),
    )


def test_collect_reconstructs_tool_use_response() -> None:
    stream = [
        {"messageStart": {"role": "assistant"}},
        {
            "contentBlockStart": {
                "contentBlockIndex": 0,
                "start": {"toolUse": {"toolUseId": "tooluse_1", "name": "shell"}},
            }
        },
        {
            "contentBlockDelta": {
                "contentBlockIndex": 0,
                "delta": {"toolUse": {"input": '{"command":"'}},
            }
        },
        {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"toolUse": {"input": 'pwd"}'}}}},
        {"contentBlockStop": {"contentBlockIndex": 0}},
        {"messageStop": {"stopReason": "tool_use"}},
        _metadata(),
    ]

    response = CollectConverseResponse().collect(stream, log_streaming=True)

    assert response == ConverseResponseModel(
        role="assistant",
        content=(
            ConverseToolUseContentBlock(
                tool_use_id="tooluse_1", name="shell", input={"command": "pwd"}
            ),
        ),
        stop_reason="tool_use",
        usage=ConverseUsageModel(10, 5, 15, None, None, ()),
        metrics=ConverseMetricsModel(latency_ms=20),
        stream=tuple(stream),
    )


def test_collect_reconstructs_text_deltas() -> None:
    stream = _text_stream()
    stream.insert(2, {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": " world"}}})

    response = CollectConverseResponse().collect(stream, log_streaming=True)

    assert response.content == (ConverseTextContentBlock(text="Hello world"),)
    assert response.stream == tuple(stream)


def test_collect_error_preserves_received_events() -> None:
    stream = _text_stream()[:-2]

    with pytest.raises(CollectConverseResponseError) as raised:
        CollectConverseResponse().collect(stream, log_streaming=True)

    assert raised.value.stream == tuple(stream)


def test_collect_does_not_retain_events_when_stream_logging_is_disabled() -> None:
    stream = _text_stream()

    response = CollectConverseResponse().collect(stream)

    assert response.content == (ConverseTextContentBlock(text="Hello"),)
    assert response.stream == ()


def test_collect_allows_incomplete_usage() -> None:
    stream = _text_stream()[:4] + [{"metadata": {"metrics": {"latencyMs": 20}}}]

    response = CollectConverseResponse().collect(stream)

    assert response.usage == ConverseUsageModel(None, None, None, None, None, ())


@pytest.mark.parametrize(
    "message_stop",
    [
        pytest.param({"messageStop": {}}, id="absent"),
        pytest.param({"messageStop": {"stopReason": None}}, id="null"),
    ],
)
def test_collect_allows_missing_finish_reason(message_stop: dict[str, object]) -> None:
    stream = _text_stream()[:3] + [message_stop, _metadata()]

    response = CollectConverseResponse().collect(stream)

    assert response.stop_reason is None


@pytest.mark.parametrize(
    ("stream", "message"),
    [
        pytest.param(_text_stream()[:-2], "ended before messageStop", id="missing-message-stop"),
        pytest.param(
            _text_stream()[:3] + [{"messageStop": {"stopReason": 1}}, _metadata()],
            "stopReason must be a string or null",
            id="invalid-stop-reason",
        ),
        pytest.param(
            _text_stream()[:2] + [{"messageStop": {"stopReason": "end_turn"}}, _metadata()],
            "unclosed content blocks: 0",
            id="unclosed-block",
        ),
        pytest.param(
            [
                {"messageStart": {"role": "assistant"}},
                {
                    "contentBlockDelta": {
                        "contentBlockIndex": 0,
                        "delta": {"toolUse": {"input": "{}"}},
                    }
                },
            ],
            "without a tool use start",
            id="tool-delta-without-start",
        ),
        pytest.param(
            [
                {"messageStart": {"role": "assistant"}},
                {
                    "contentBlockStart": {
                        "contentBlockIndex": 0,
                        "start": {"toolUse": {"toolUseId": "id", "name": "shell"}},
                    }
                },
                {
                    "contentBlockDelta": {
                        "contentBlockIndex": 0,
                        "delta": {"toolUse": {"input": "{"}},
                    }
                },
                {"contentBlockStop": {"contentBlockIndex": 0}},
                {"messageStop": {"stopReason": "tool_use"}},
                _metadata(),
            ],
            "invalid JSON input",
            id="invalid-tool-json",
        ),
        pytest.param(
            _text_stream()[:4] + [{"messageStop": {"stopReason": "end_turn"}}],
            "multiple messageStop",
            id="duplicate-message-stop",
        ),
        pytest.param(
            _text_stream()[:3]
            + [{"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "again"}}}],
            "after closing",
            id="delta-after-stop",
        ),
        pytest.param(
            _text_stream()[:3] + [{"contentBlockStop": {"contentBlockIndex": 0}}],
            "more than once",
            id="duplicate-block-stop",
        ),
        pytest.param(
            _text_stream()[:4]
            + [{"contentBlockDelta": {"contentBlockIndex": 1, "delta": {"text": "late"}}}],
            "after messageStop",
            id="content-after-message-stop",
        ),
        pytest.param(
            _text_stream()[:1] + [_metadata()],
            "metadata received before messageStop",
            id="metadata-before-stop",
        ),
        pytest.param(
            [
                {"messageStart": {"role": "assistant"}},
                {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"reasoningContent": {}}}},
            ],
            "unsupported delta type",
            id="unsupported-delta",
        ),
        pytest.param(_text_stream()[:-1], "ended without metadata", id="missing-metadata"),
    ],
)
def test_collect_rejects_incomplete_or_invalid_stream(stream: list[object], message: str) -> None:
    with pytest.raises(CollectConverseResponseError, match=message):
        CollectConverseResponse().collect(stream)
