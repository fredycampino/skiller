from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Generic, TypeAlias, TypeVar

from skiller.domain.agent.agent_llm_generation_model import LLMToolChoiceMode

DEFAULT_AGENT_LLM_PARALLEL_TOOL_CALLS = True
DEFAULT_AGENT_LLM_TOOL_CHOICE = LLMToolChoiceMode.AUTO
MINIMAX_LLM_TEMPERATURE = 1
MINIMAX_LLM_TOP_P = 1
MINIMAX_LLM_MAX_OUTPUT_TOKENS = 4096


class AgentLLMProviderType(str, Enum):
    NULL = "null"
    FAKE = "fake"
    MINIMAX = "minimax"
    CODEX = "codex"


class AgentLLMModelEnum(str, Enum):
    model_context_window_tokens: int

    def __new__(
        cls,
        value: str,
        model_context_window_tokens: int,
    ) -> "AgentLLMModelEnum":
        item = str.__new__(cls, value)
        item._value_ = value
        item.model_context_window_tokens = model_context_window_tokens
        return item


class AgentNullLLMModel(AgentLLMModelEnum):
    NULL1 = ("null1", 100_000)


class AgentFakeLLMModel(AgentLLMModelEnum):
    MODEL1 = ("model1", 100_000)


class AgentMiniMaxLLMModel(AgentLLMModelEnum):
    M2_5 = ("MiniMax-M2.5", 204_800)
    M2_7 = ("MiniMax-M2.7", 204_800)


class AgentCodexLLMModel(AgentLLMModelEnum):
    GPT_5_3_CODEX = ("gpt-5.3-codex", 400_000)
    GPT_5_4 = ("gpt-5.4", 1_050_000)
    GPT_5_5 = ("gpt-5.5", 1_050_000)


AgentLLMModel: TypeAlias = (
    AgentNullLLMModel
    | AgentFakeLLMModel
    | AgentMiniMaxLLMModel
    | AgentCodexLLMModel
)


def agent_llm_model_from_value(value: str) -> AgentLLMModel:
    model_types = (
        AgentNullLLMModel,
        AgentFakeLLMModel,
        AgentMiniMaxLLMModel,
        AgentCodexLLMModel,
    )
    for model_type in model_types:
        try:
            return model_type(value)
        except ValueError:
            continue

    raise ValueError(f"Unsupported LLM model: {value}")

ModelT = TypeVar(
    "ModelT",
    AgentNullLLMModel,
    AgentFakeLLMModel,
    AgentMiniMaxLLMModel,
    AgentCodexLLMModel,
)


@dataclass(frozen=True)
class AgentLLMProviderConfig(Generic[ModelT]):
    model: ModelT
    timeout_seconds: float
    window_width_tokens: int

    parallel_tool_calls: ClassVar[bool] = DEFAULT_AGENT_LLM_PARALLEL_TOOL_CALLS
    tool_choice: ClassVar[LLMToolChoiceMode] = DEFAULT_AGENT_LLM_TOOL_CHOICE


@dataclass(frozen=True)
class AgentNullProvider(AgentLLMProviderConfig[AgentNullLLMModel]):
    type: ClassVar[AgentLLMProviderType] = AgentLLMProviderType.NULL

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentNullLLMModel):
            raise TypeError("Null LLM provider model must be an AgentNullLLMModel")


@dataclass(frozen=True)
class AgentFakeProvider(AgentLLMProviderConfig[AgentFakeLLMModel]):
    type: ClassVar[AgentLLMProviderType] = AgentLLMProviderType.FAKE

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentFakeLLMModel):
            raise TypeError("Fake LLM provider model must be an AgentFakeLLMModel")


@dataclass(frozen=True)
class AgentMiniMaxProvider(AgentLLMProviderConfig[AgentMiniMaxLLMModel]):
    api_key: str

    temperature: ClassVar[float] = MINIMAX_LLM_TEMPERATURE
    top_p: ClassVar[float] = MINIMAX_LLM_TOP_P
    max_output_tokens: ClassVar[int] = MINIMAX_LLM_MAX_OUTPUT_TOKENS
    type: ClassVar[AgentLLMProviderType] = AgentLLMProviderType.MINIMAX

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentMiniMaxLLMModel):
            raise TypeError("MiniMax LLM provider model must be an AgentMiniMaxLLMModel")


@dataclass(frozen=True)
class AgentCodexProvider(AgentLLMProviderConfig[AgentCodexLLMModel]):
    credentials_file: str

    type: ClassVar[AgentLLMProviderType] = AgentLLMProviderType.CODEX

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentCodexLLMModel):
            raise TypeError("Codex LLM provider model must be an AgentCodexLLMModel")


AgentLLMProvider: TypeAlias = (
    AgentNullProvider | AgentFakeProvider | AgentMiniMaxProvider | AgentCodexProvider
)


@dataclass(frozen=True)
class AgentLLMProviderList:
    default_provider: AgentLLMProviderType
    providers: tuple[AgentLLMProvider, ...]

    def __post_init__(self) -> None:
        if not self.providers:
            raise RuntimeError("LLM providers must not be empty")

        for provider in self.providers:
            if provider.type == self.default_provider:
                return

        raise RuntimeError(
            f"Missing default LLM provider config: {self.default_provider.value}"
        )

    def default(self) -> AgentLLMProvider:
        for provider in self.providers:
            if provider.type == self.default_provider:
                return provider

        raise RuntimeError(
            f"Missing default LLM provider config: {self.default_provider.value}"
        )
