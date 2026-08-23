from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from skiller.infrastructure.llm.bedrock.converse_response_model import (
    ConverseCacheDetailModel,
    ConverseContentBlock,
    ConverseMetricsModel,
    ConverseResponseModel,
    ConverseTextContentBlock,
    ConverseToolUseContentBlock,
    ConverseUsageModel,
)


class CollectConverseResponseError(ValueError):
    def __init__(self, message: str, *, stream: tuple[object, ...] = ()) -> None:
        super().__init__(message)
        self.stream = stream


@dataclass
class _ContentBlock:
    kind: str
    text_chunks: list[str] = field(default_factory=list)
    tool_use_id: str | None = None
    name: str | None = None
    input_chunks: list[str] = field(default_factory=list)
    stopped: bool = False


class CollectConverseResponse:
    def collect(self, stream: object, *, log_streaming: bool = False) -> ConverseResponseModel:
        events: list[object] = []
        try:
            return self._collect(
                stream=stream,
                events=events,
                log_streaming=log_streaming,
            )
        except CollectConverseResponseError as exc:
            raise CollectConverseResponseError(str(exc), stream=tuple(events)) from exc

    def _collect(
        self,
        *,
        stream: object,
        events: list[object],
        log_streaming: bool,
    ) -> ConverseResponseModel:
        if not isinstance(stream, Iterable):
            raise CollectConverseResponseError("Bedrock stream must be iterable", stream=())

        role: str | None = None
        stop_reason: str | None = None
        message_stopped = False
        usage: ConverseUsageModel | None = None
        metrics: ConverseMetricsModel | None = None
        blocks: dict[int, _ContentBlock] = {}

        for event in stream:
            if log_streaming:
                events.append(event)
            if not isinstance(event, Mapping):
                raise CollectConverseResponseError(
                    "Bedrock stream event must be a JSON object", stream=()
                )
            event_names = [
                name
                for name in (
                    "messageStart",
                    "contentBlockStart",
                    "contentBlockDelta",
                    "contentBlockStop",
                    "messageStop",
                    "metadata",
                )
                if name in event
            ]
            if len(event_names) != 1:
                raise CollectConverseResponseError(
                    "Bedrock stream event must contain exactly one supported event type"
                )
            event_name = event_names[0]
            payload = event[event_name]
            if not isinstance(payload, Mapping):
                raise CollectConverseResponseError(
                    f"Bedrock stream {event_name} event must be a JSON object"
                )

            if event_name == "messageStart":
                if role is not None:
                    raise CollectConverseResponseError(
                        "Bedrock stream contains multiple messageStart events"
                    )
                raw_role = payload.get("role")
                if not isinstance(raw_role, str):
                    raise CollectConverseResponseError(
                        "Bedrock stream messageStart role must be a string"
                    )
                role = raw_role
                continue

            if role is None:
                raise CollectConverseResponseError(
                    f"Bedrock stream received {event_name} before messageStart"
                )
            if message_stopped and event_name == "messageStop":
                raise CollectConverseResponseError(
                    "Bedrock stream contains multiple messageStop events"
                )
            if message_stopped and event_name != "metadata":
                raise CollectConverseResponseError(
                    f"Bedrock stream received {event_name} after messageStop"
                )

            if event_name == "contentBlockStart":
                index = _index(payload, event_name)
                start = payload.get("start")
                tool_use = start.get("toolUse") if isinstance(start, Mapping) else None
                if not isinstance(tool_use, Mapping):
                    raise CollectConverseResponseError(
                        f"Bedrock stream content block index {index} has unsupported start type"
                    )
                tool_use_id = tool_use.get("toolUseId")
                name = tool_use.get("name")
                if tool_use_id is not None and not isinstance(tool_use_id, str):
                    raise CollectConverseResponseError(
                        f"Bedrock stream tool use at content block index {index} "
                        "has an invalid toolUseId"
                    )
                if name is not None and not isinstance(name, str):
                    raise CollectConverseResponseError(
                        f"Bedrock stream tool use at content block index {index} "
                        "has an invalid name"
                    )
                if index in blocks:
                    raise CollectConverseResponseError(
                        f"Bedrock stream started content block index {index} more than once"
                    )
                blocks[index] = _ContentBlock(kind="tool_use", tool_use_id=tool_use_id, name=name)
                continue

            if event_name == "contentBlockDelta":
                index = _index(payload, event_name)
                delta = payload.get("delta")
                if not isinstance(delta, Mapping):
                    raise CollectConverseResponseError(
                        f"Bedrock stream content block index {index} has an invalid delta"
                    )
                block = blocks.get(index)
                if block is not None and block.stopped:
                    raise CollectConverseResponseError(
                        f"Bedrock stream received a delta after closing content block index {index}"
                    )
                if "text" in delta:
                    text = delta["text"]
                    if not isinstance(text, str):
                        raise CollectConverseResponseError(
                            f"Bedrock stream text delta at content block index {index} "
                            "must be a string"
                        )
                    if block is None:
                        block = _ContentBlock(kind="text")
                        blocks[index] = block
                    if block.kind != "text":
                        raise CollectConverseResponseError(
                            f"Bedrock stream content block index {index} "
                            "changed from tool use to text"
                        )
                    block.text_chunks.append(text)
                    continue
                tool_use = delta.get("toolUse")
                if not isinstance(tool_use, Mapping):
                    raise CollectConverseResponseError(
                        f"Bedrock stream content block index {index} has unsupported delta type"
                    )
                if block is None or block.kind != "tool_use":
                    raise CollectConverseResponseError(
                        "Bedrock stream received a tool use delta without a tool use start "
                        f"at content block index {index}"
                    )
                input_chunk = tool_use.get("input")
                if not isinstance(input_chunk, str):
                    raise CollectConverseResponseError(
                        f"Bedrock stream tool use delta at content block index {index} "
                        "is missing input"
                    )
                block.input_chunks.append(input_chunk)
                continue

            if event_name == "contentBlockStop":
                index = _index(payload, event_name)
                block = blocks.get(index)
                if block is None:
                    raise CollectConverseResponseError(
                        f"Bedrock stream closed unknown content block index {index}"
                    )
                if block.stopped:
                    raise CollectConverseResponseError(
                        f"Bedrock stream closed content block index {index} more than once"
                    )
                block.stopped = True
                continue

            if event_name == "messageStop":
                if message_stopped:
                    raise CollectConverseResponseError(
                        "Bedrock stream contains multiple messageStop events"
                    )
                open_indexes = [str(index) for index, block in blocks.items() if not block.stopped]
                if open_indexes:
                    raise CollectConverseResponseError(
                        "Bedrock stream ended with unclosed content blocks: "
                        f"{', '.join(open_indexes)}"
                    )
                raw_stop_reason = payload.get("stopReason")
                if raw_stop_reason is None:
                    pass
                elif isinstance(raw_stop_reason, str):
                    stop_reason = raw_stop_reason
                else:
                    raise CollectConverseResponseError(
                        "Bedrock stream messageStop stopReason must be a string or null"
                    )
                message_stopped = True
                continue

            if not message_stopped:
                raise CollectConverseResponseError(
                    "Bedrock stream metadata received before messageStop"
                )
            if usage is not None:
                raise CollectConverseResponseError(
                    "Bedrock stream contains multiple metadata events"
                )
            usage = _usage(payload.get("usage"))
            metrics = _metrics(payload.get("metrics"))

        if role is None:
            raise CollectConverseResponseError("Bedrock stream ended without messageStart event")
        if not message_stopped:
            raise CollectConverseResponseError("Bedrock stream ended before messageStop event")
        if usage is None or metrics is None:
            raise CollectConverseResponseError("Bedrock stream ended without metadata event")

        content: list[ConverseContentBlock] = []
        for index in sorted(blocks):
            block = blocks[index]
            if block.kind == "text":
                content.append(ConverseTextContentBlock(text="".join(block.text_chunks)))
                continue
            raw_input = "".join(block.input_chunks)
            try:
                input_value = json.loads(raw_input)
            except json.JSONDecodeError as exc:
                raise CollectConverseResponseError(
                    f"Bedrock stream tool use at content block index {index} has invalid JSON input"
                ) from exc
            content.append(
                ConverseToolUseContentBlock(
                    tool_use_id=block.tool_use_id,
                    name=block.name,
                    input=input_value,
                )
            )
        return ConverseResponseModel(
            role=role,
            content=tuple(content),
            stop_reason=stop_reason,
            usage=usage,
            metrics=metrics,
            stream=tuple(events),
        )


def _index(payload: Mapping[str, object], event_name: str) -> int:
    index = payload.get("contentBlockIndex")
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise CollectConverseResponseError(
            f"Bedrock stream {event_name} is missing a valid contentBlockIndex", stream=()
        )
    return index


def _usage(raw_usage: object) -> ConverseUsageModel:
    if not isinstance(raw_usage, Mapping):
        return ConverseUsageModel(None, None, None, None, None, ())
    cache_details: list[ConverseCacheDetailModel] = []
    raw_details = raw_usage.get("cacheDetails", [])
    if isinstance(raw_details, list):
        for detail in raw_details:
            if not isinstance(detail, Mapping):
                continue
            ttl = detail.get("ttl")
            input_tokens = _optional_usage_int(detail.get("inputTokens"))
            if not isinstance(ttl, str) or input_tokens is None:
                continue
            cache_details.append(ConverseCacheDetailModel(ttl=ttl, input_tokens=input_tokens))
    return ConverseUsageModel(
        input_tokens=_optional_usage_int(raw_usage.get("inputTokens")),
        output_tokens=_optional_usage_int(raw_usage.get("outputTokens")),
        total_tokens=_optional_usage_int(raw_usage.get("totalTokens")),
        cache_read_input_tokens=_optional_usage_int(raw_usage.get("cacheReadInputTokens")),
        cache_write_input_tokens=_optional_usage_int(raw_usage.get("cacheWriteInputTokens")),
        cache_details=tuple(cache_details),
    )


def _optional_usage_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _metrics(raw_metrics: object) -> ConverseMetricsModel:
    if not isinstance(raw_metrics, Mapping):
        raise CollectConverseResponseError("Bedrock stream metadata is missing metrics")
    latency_ms = raw_metrics.get("latencyMs")
    if isinstance(latency_ms, bool) or not isinstance(latency_ms, int) or latency_ms < 0:
        raise CollectConverseResponseError("Bedrock stream metadata has invalid latencyMs")
    return ConverseMetricsModel(latency_ms=latency_ms)
