from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True)
class ConverseTextContentBlock:
    text: str


@dataclass(frozen=True)
class ConverseToolUseContentBlock:
    tool_use_id: str | None
    name: str | None
    input: JsonValue


ConverseContentBlock = ConverseTextContentBlock | ConverseToolUseContentBlock


@dataclass(frozen=True)
class ConverseCacheDetailModel:
    ttl: str
    input_tokens: int


@dataclass(frozen=True)
class ConverseUsageModel:
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    cache_read_input_tokens: int | None
    cache_write_input_tokens: int | None
    cache_details: tuple[ConverseCacheDetailModel, ...]


@dataclass(frozen=True)
class ConverseMetricsModel:
    latency_ms: int


@dataclass(frozen=True)
class ConverseResponseModel:
    role: str
    content: tuple[ConverseContentBlock, ...]
    stop_reason: str | None
    usage: ConverseUsageModel
    metrics: ConverseMetricsModel
    stream: tuple[object, ...]
