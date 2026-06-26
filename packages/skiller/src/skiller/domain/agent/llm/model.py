from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Mapping, Protocol, TypeAlias, runtime_checkable


@runtime_checkable
class LLMModelLike(Protocol):
    value: str
    model_context_window_tokens: int


def validate_llm_model_like(value: object, *, label: str) -> LLMModelLike:
    if not isinstance(value, LLMModelLike):
        raise TypeError(f"{label} must be an LLMModelLike")
    if not isinstance(value.value, str) or not value.value.strip():
        raise TypeError(f"{label} value must be a non-empty string")
    if (
        not isinstance(value.model_context_window_tokens, int)
        or value.model_context_window_tokens <= 0
    ):
        raise TypeError(f"{label} context window must be a positive integer")
    return value


@dataclass(frozen=True)
class LLMCustomModel:
    value: str
    model_context_window_tokens: int

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("LLM custom model requires value")
        if self.model_context_window_tokens <= 0:
            raise ValueError("LLM custom model requires positive context window")


class LLMStaticModel(str, Enum):
    _model_context_window_tokens: int

    def __new__(
        cls,
        value: str,
        model_context_window_tokens: int,
    ) -> "LLMStaticModel":
        item = str.__new__(cls, value)
        item._value_ = value
        item._model_context_window_tokens = model_context_window_tokens
        return item

    @property
    def model_context_window_tokens(self) -> int:
        return self._model_context_window_tokens


class LLMToolChoiceMode(str, Enum):
    AUTO = "auto"
    NONE = "none"
    REQUIRED = "required"


class AgentLLMProviderType(str, Enum):
    NULL = "null"
    FAKE = "fake"
    MINIMAX = "minimax"
    LMSTUDIO = "lmstudio"
    CODEX = "codex"
    BEDROCK = "bedrock"


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
    model: str | None = None

    def __post_init__(self) -> None:
        if self.provider is not None:
            object.__setattr__(self, "provider", AgentLLMProviderType(self.provider))
        if self.model is not None:
            object.__setattr__(self, "model", _usage_model_value(self.model))


def _usage_model_value(value: object) -> str:
    if isinstance(value, LLMModelLike):
        return value.value
    if isinstance(value, str) and value.strip():
        return value
    raise TypeError("LLMUsage model must be a non-empty string")


@dataclass(frozen=True)
class LLMResponse:
    ok: bool
    model: LLMModelLike
    content: str | None = None
    tool_calls: tuple[LLMToolCall, ...] = ()
    finish_reason: str | None = None
    usage: LLMUsage | None = None
    error: str | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        validate_llm_model_like(self.model, label="LLMResponse model")
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
