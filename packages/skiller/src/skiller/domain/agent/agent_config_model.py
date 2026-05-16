from dataclasses import dataclass, field
from enum import Enum


class AgentLLMProviderType(str, Enum):
    NULL = "null"
    FAKE = "fake"
    MINIMAX = "minimax"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class AgentLLMClientType(str, Enum):
    NULL = "null"
    FAKE = "fake"
    OPENAI_CHAT_COMPLETIONS = "openai_chat_completions"
    ANTHROPIC_MESSAGES = "anthropic_messages"
    GEMINI_NATIVE = "gemini_native"


@dataclass(frozen=True)
class AgentLLMProviderConfig:
    provider: AgentLLMProviderType
    client_type: AgentLLMClientType
    model: str
    api_key: str
    base_url: str
    timeout_seconds: float
    context_window_tokens: int


@dataclass(frozen=True)
class AgentLLMConfig:
    default_provider: str
    providers: dict[str, AgentLLMProviderConfig]

    def __post_init__(self) -> None:
        if not self.providers:
            raise RuntimeError("LLM providers must not be empty")

        if self.default_provider not in self.providers:
            raise RuntimeError(f"Missing default LLM provider config: {self.default_provider}")

    def default(self) -> AgentLLMProviderConfig:
        return self.providers[self.default_provider]


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
