from dataclasses import dataclass, field

from skiller.domain.agent.llm.provider_registry import AgentLLMProviderList
from skiller.domain.tool.tool_contract import ToolRuntimeConfigs


@dataclass(frozen=True)
class AgentLoopConfig:
    max_turns: int
    max_tool_calls: int


@dataclass(frozen=True)
class AgentContextCompactionConfig:
    enabled: bool
    max_total_tokens_ratio: float
    keep_last: int


@dataclass(frozen=True)
class AgentContextConfig:
    compaction: AgentContextCompactionConfig


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
class AgentConfig:
    llm: AgentLLMProviderList
    loop: AgentLoopConfig
    context: AgentContextConfig
    event_output: AgentEventOutputConfig
    tools: ToolRuntimeConfigs = field(default_factory=ToolRuntimeConfigs)
