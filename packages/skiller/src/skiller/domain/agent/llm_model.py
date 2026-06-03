from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Mapping, TypeAlias

from skiller.domain.agent.agent_llm_provider_model import (
    AgentLLMModel,
    AgentLLMModelEnum,
    AgentLLMProviderType,
)


class LLMMessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


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
class LLMSystemMessage:
    content: str
    name: str | None = None
    role: Literal[LLMMessageRole.SYSTEM] = field(
        default=LLMMessageRole.SYSTEM,
        init=False,
    )


@dataclass(frozen=True)
class LLMUserMessage:
    content: str
    name: str | None = None
    role: Literal[LLMMessageRole.USER] = field(
        default=LLMMessageRole.USER,
        init=False,
    )


@dataclass(frozen=True)
class LLMAssistantMessage:
    content: str | None = None
    name: str | None = None
    tool_calls: tuple[LLMToolCall, ...] = ()
    role: Literal[LLMMessageRole.ASSISTANT] = field(
        default=LLMMessageRole.ASSISTANT,
        init=False,
    )

    def __post_init__(self) -> None:
        if self.content is None and not self.tool_calls:
            raise ValueError("Assistant messages require content or tool calls")


@dataclass(frozen=True)
class LLMToolMessage:
    content: str
    tool_call_id: str
    name: str | None = None
    role: Literal[LLMMessageRole.TOOL] = field(
        default=LLMMessageRole.TOOL,
        init=False,
    )


LLMMessage: TypeAlias = (
    LLMSystemMessage
    | LLMUserMessage
    | LLMAssistantMessage
    | LLMToolMessage
)


@dataclass(frozen=True)
class LLMResponseFormat:
    type: LLMResponseFormatType
    json_schema_name: str | None = None
    json_schema: Mapping[str, object] | None = None
    strict: bool | None = None


@dataclass(frozen=True)
class LLMUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    provider: AgentLLMProviderType | None = None
    model: AgentLLMModel | None = None

    def __post_init__(self) -> None:
        if self.provider is not None:
            object.__setattr__(self, "provider", AgentLLMProviderType(self.provider))
        if self.model is not None and not isinstance(self.model, AgentLLMModelEnum):
            raise TypeError("LLMUsage model must be an AgentLLMModel enum")


@dataclass(frozen=True)
class LLMResponse:
    ok: bool
    model: AgentLLMModel
    content: str | None = None
    tool_calls: tuple[LLMToolCall, ...] = ()
    finish_reason: str | None = None
    usage: LLMUsage | None = None
    error: str | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentLLMModelEnum):
            raise TypeError("LLMResponse model must be an AgentLLMModel enum")
        object.__setattr__(self, "content", _clean_optional_string(self.content))
        object.__setattr__(
            self,
            "finish_reason",
            _clean_optional_string(self.finish_reason),
        )
        object.__setattr__(self, "error", _clean_optional_string(self.error))
        object.__setattr__(self, "error_code", _clean_optional_string(self.error_code))

    @property
    def has_text_content(self) -> bool:
        return self.content is not None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)

    @property
    def is_error(self) -> bool:
        return self.ok is False


def _clean_optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned
