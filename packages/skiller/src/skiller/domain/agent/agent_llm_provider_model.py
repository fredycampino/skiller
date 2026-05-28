from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, TypeAlias


class AgentLLMProviderType(str, Enum):
    NULL = "null"
    FAKE = "fake"
    MINIMAX = "minimax"
    CODEX = "codex"


class AgentNullLLMModel(str, Enum):
    NULL1 = "null1"


class AgentFakeLLMModel(str, Enum):
    MODEL1 = "model1"


class AgentMiniMaxLLMModel(str, Enum):
    M2_5 = "MiniMax-M2.5"
    M2_7 = "MiniMax-M2.7"


class AgentCodexLLMModel(str, Enum):
    GPT_5_3_CODEX = "gpt-5.3-codex"
    GPT_5_4 = "gpt-5.4"
    GPT_5_5 = "gpt-5.5"


AgentLLMModel: TypeAlias = (
    AgentNullLLMModel
    | AgentFakeLLMModel
    | AgentMiniMaxLLMModel
    | AgentCodexLLMModel
)


@dataclass(frozen=True)
class AgentNullProvider:
    model: AgentNullLLMModel
    timeout_seconds: float
    context_window_tokens: int

    type: ClassVar[AgentLLMProviderType] = AgentLLMProviderType.NULL


@dataclass(frozen=True)
class AgentFakeProvider:
    model: AgentFakeLLMModel
    timeout_seconds: float
    context_window_tokens: int

    type: ClassVar[AgentLLMProviderType] = AgentLLMProviderType.FAKE


@dataclass(frozen=True)
class AgentMiniMaxProvider:
    model: AgentMiniMaxLLMModel
    api_key: str
    timeout_seconds: float
    context_window_tokens: int

    type: ClassVar[AgentLLMProviderType] = AgentLLMProviderType.MINIMAX


@dataclass(frozen=True)
class AgentCodexProvider:
    model: AgentCodexLLMModel
    credentials_file: str
    timeout_seconds: float
    context_window_tokens: int

    type: ClassVar[AgentLLMProviderType] = AgentLLMProviderType.CODEX


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
