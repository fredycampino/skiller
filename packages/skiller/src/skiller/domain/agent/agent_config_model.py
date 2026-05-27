from dataclasses import dataclass, field
from enum import Enum

from skiller.domain.tool.tool_contract import ToolRuntimeConfigs


class AgentLLMProviderType(str, Enum):
    NULL = "null"
    FAKE = "fake"
    MINIMAX = "minimax"
    CODEX = "codex"


@dataclass(frozen=True)
class AgentLLMProviderConfig:
    provider_type: AgentLLMProviderType
    model: str
    api_key: str | None
    timeout_seconds: float
    context_window_tokens: int
    credentials_file: str | None = None


@dataclass(frozen=True)
class AgentLLMConfig:
    default_provider: AgentLLMProviderType
    providers: tuple[AgentLLMProviderConfig, ...]

    def __post_init__(self) -> None:
        if not self.providers:
            raise RuntimeError("LLM providers must not be empty")

        for provider in self.providers:
            if provider.provider_type == self.default_provider:
                return

        raise RuntimeError(
            f"Missing default LLM provider config: {self.default_provider.value}"
        )

    def default(self) -> AgentLLMProviderConfig:
        for provider in self.providers:
            if provider.provider_type == self.default_provider:
                return provider

        raise RuntimeError(
            f"Missing default LLM provider config: {self.default_provider.value}"
        )


@dataclass(frozen=True)
class AgentLoopConfig:
    max_turns: int = 10
    max_tool_calls: int = 5


@dataclass(frozen=True)
class AgentContextCompactionConfig:
    enabled: bool = False
    max_total_tokens_ratio: float = 0.8


@dataclass(frozen=True)
class AgentContextConfig:
    compaction: AgentContextCompactionConfig = field(
        default_factory=AgentContextCompactionConfig,
    )


@dataclass(frozen=True)
class AgentEventOutputTruncateConfig:
    enabled: bool = True
    max_text_chars: int = 600
    max_json_chars: int = 4000
    max_array_items: int = 20


@dataclass(frozen=True)
class AgentEventOutputConfig:
    truncate: AgentEventOutputTruncateConfig = field(
        default_factory=AgentEventOutputTruncateConfig,
    )


@dataclass(frozen=True)
class AgentConfig:
    llm: AgentLLMConfig
    loop: AgentLoopConfig = field(default_factory=AgentLoopConfig)
    context: AgentContextConfig = field(default_factory=AgentContextConfig)
    event_output: AgentEventOutputConfig = field(default_factory=AgentEventOutputConfig)
    tools: ToolRuntimeConfigs = field(default_factory=ToolRuntimeConfigs)
