from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol

from skiller.domain.tool.tool_contract import ToolConfig


class LLMMessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class LLMToolChoiceMode(str, Enum):
    AUTO = "auto"
    NONE = "none"
    REQUIRED = "required"


class LLMResponseFormatType(str, Enum):
    TEXT = "text"
    JSON_OBJECT = "json_object"
    JSON_SCHEMA = "json_schema"


@dataclass(frozen=True)
class LLMToolCallFunction:
    name: str
    arguments_json: str


@dataclass(frozen=True)
class LLMToolCall:
    id: str
    function: LLMToolCallFunction


@dataclass(frozen=True)
class LLMMessage:
    role: LLMMessageRole
    content: str | None = None
    name: str | None = None
    tool_calls: tuple[LLMToolCall, ...] = ()
    tool_call_id: str | None = None

    def __post_init__(self) -> None:
        if self.role != LLMMessageRole.ASSISTANT and self.tool_calls:
            raise ValueError("Only assistant messages can carry tool calls")
        if self.role == LLMMessageRole.TOOL and not self.tool_call_id:
            raise ValueError("Tool messages require tool_call_id")
        if self.role != LLMMessageRole.TOOL and self.tool_call_id is not None:
            raise ValueError("Only tool messages can carry tool_call_id")

    @classmethod
    def system(cls, content: str, *, name: str | None = None) -> "LLMMessage":
        return cls(role=LLMMessageRole.SYSTEM, content=content, name=name)

    @classmethod
    def user(cls, content: str, *, name: str | None = None) -> "LLMMessage":
        return cls(role=LLMMessageRole.USER, content=content, name=name)

    @classmethod
    def assistant(
        cls,
        content: str | None = None,
        *,
        name: str | None = None,
        tool_calls: tuple[LLMToolCall, ...] = (),
    ) -> "LLMMessage":
        return cls(
            role=LLMMessageRole.ASSISTANT,
            content=content,
            name=name,
            tool_calls=tool_calls,
        )

    @classmethod
    def tool(
        cls,
        content: str,
        *,
        tool_call_id: str,
        name: str | None = None,
    ) -> "LLMMessage":
        return cls(
            role=LLMMessageRole.TOOL,
            content=content,
            name=name,
            tool_call_id=tool_call_id,
        )


@dataclass(frozen=True)
class LLMToolChoice:
    mode: LLMToolChoiceMode
    tool_name: str | None = None

    @classmethod
    def auto(cls) -> "LLMToolChoice":
        return cls(mode=LLMToolChoiceMode.AUTO)

    @classmethod
    def none(cls) -> "LLMToolChoice":
        return cls(mode=LLMToolChoiceMode.NONE)

    @classmethod
    def required(cls) -> "LLMToolChoice":
        return cls(mode=LLMToolChoiceMode.REQUIRED)

    @classmethod
    def tool(cls, tool_name: str) -> "LLMToolChoice":
        return cls(mode=LLMToolChoiceMode.REQUIRED, tool_name=tool_name)


@dataclass(frozen=True)
class LLMResponseFormat:
    type: LLMResponseFormatType
    json_schema_name: str | None = None
    json_schema: Mapping[str, object] | None = None
    strict: bool | None = None


@dataclass(frozen=True)
class LLMRequest:
    messages: tuple[LLMMessage, ...]
    model: str | None = None
    tools: tuple[ToolConfig, ...] = ()
    tool_choice: LLMToolChoice | None = None
    response_format: LLMResponseFormat | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    parallel_tool_calls: bool | None = None


@dataclass(frozen=True)
class LLMResponse:
    ok: bool
    content: str | None = None
    model: str | None = None
    tool_calls: tuple[LLMToolCall, ...] = ()
    finish_reason: str | None = None
    error: str | None = None


class LLMPort(Protocol):
    def generate(self, request: LLMRequest) -> LLMResponse: ...


ChatCompletionsPort = LLMPort

__all__ = [
    "ChatCompletionsPort",
    "LLMMessage",
    "LLMMessageRole",
    "LLMPort",
    "LLMRequest",
    "LLMResponse",
    "LLMResponseFormat",
    "LLMResponseFormatType",
    "LLMToolCall",
    "LLMToolCallFunction",
    "LLMToolChoice",
    "LLMToolChoiceMode",
]
