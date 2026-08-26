from dataclasses import dataclass, field

from skiller.domain.agent.context.model import AgentContextMetrics
from skiller.domain.tool.tool_contract import ToolRuntimeConfigs

TOOL_RESULT_APPROX_BYTES_PER_TOKEN = 4
TOOL_RESULT_CONTEXT_RATIO = 0.10
TOOL_RESULT_MAX_BYTES = 50_000


@dataclass(frozen=True)
class AgentLoopConfig:
    max_turns: int
    max_tool_calls: int


@dataclass(frozen=True)
class AgentLLMSelection:
    provider: str
    model: str

    def __post_init__(self) -> None:
        if not self.provider:
            raise ValueError("Agent LLM selection requires provider")
        if not self.model:
            raise ValueError("Agent LLM selection requires model")


@dataclass(frozen=True)
class AgentContextCompactionConfig:
    compaction_trigger_ratio: float
    compaction_target_ratio: float
    keep_last_blocks: int


@dataclass(frozen=True)
class AgentContextConfig:
    window_width_tokens: int | None
    compaction: AgentContextCompactionConfig

    def metrics(self, *, model_context_window_tokens: int) -> AgentContextMetrics:
        return AgentContextMetrics(
            effective_window_tokens=self.effective_context_tokens(
                model_context_window_tokens=model_context_window_tokens,
            ),
            max_total_tokens_ratio=self.compaction.compaction_trigger_ratio,
            window_width_tokens=self.window_width_tokens,
            model_context_window_tokens=model_context_window_tokens,
        )

    def effective_context_tokens(self, *, model_context_window_tokens: int) -> int:
        if self.window_width_tokens is None:
            return model_context_window_tokens
        return min(
            self.window_width_tokens,
            model_context_window_tokens,
        )

    def compaction_trigger_tokens(self, *, model_context_window_tokens: int) -> int:
        effective_context_tokens = self.effective_context_tokens(
            model_context_window_tokens=model_context_window_tokens,
        )
        return int(effective_context_tokens * self.compaction.compaction_trigger_ratio)

    def compaction_target_tokens(self, *, model_context_window_tokens: int) -> int:
        effective_context_tokens = self.effective_context_tokens(
            model_context_window_tokens=model_context_window_tokens,
        )
        return int(effective_context_tokens * self.compaction.compaction_target_ratio)

    def tool_result_max_bytes(self, *, model_context_window_tokens: int) -> int:
        effective_context_tokens = self.effective_context_tokens(
            model_context_window_tokens=model_context_window_tokens,
        )
        return min(
            TOOL_RESULT_MAX_BYTES,
            int(
                effective_context_tokens
                * TOOL_RESULT_CONTEXT_RATIO
                * TOOL_RESULT_APPROX_BYTES_PER_TOKEN
            ),
        )


@dataclass(frozen=True)
class AgentEventOutputTruncateConfig:
    enabled: bool
    max_text_chars: int
    max_json_chars: int
    max_array_items: int


@dataclass(frozen=True)
class AgentEventOutputConfig:
    truncate: AgentEventOutputTruncateConfig


@dataclass(frozen=True)
class AgentDebugConfig:
    log_request: bool
    log_request_file: str | None
    log_override_file: bool
    log_streaming: bool = False


@dataclass(frozen=True)
class AgentConfig:
    llm: AgentLLMSelection
    loop: AgentLoopConfig
    context: AgentContextConfig
    event_output: AgentEventOutputConfig
    debug: AgentDebugConfig
    tools: ToolRuntimeConfigs = field(default_factory=ToolRuntimeConfigs)
