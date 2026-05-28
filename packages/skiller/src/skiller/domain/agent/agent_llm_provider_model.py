from dataclasses import dataclass
from enum import Enum


class AgentLLMProviderType(str, Enum):
    NULL = "null"
    FAKE = "fake"
    MINIMAX = "minimax"
    CODEX = "codex"


class AgentLLMModel(str, Enum):
    NULL1 = "null1"
    MODEL1 = "model1"
    MINIMAX_M2_5 = "MiniMax-M2.5"
    MINIMAX_M2_7 = "MiniMax-M2.7"
    GPT_5_3_CODEX = "gpt-5.3-codex"
    GPT_5_4 = "gpt-5.4"
    GPT_5_5 = "gpt-5.5"


@dataclass(frozen=True)
class AgentLLMProvider:
    type: AgentLLMProviderType
    model: AgentLLMModel
    api_key: str | None
    timeout_seconds: float
    context_window_tokens: int
    credentials_file: str | None = None


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
