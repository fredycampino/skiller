from dataclasses import dataclass, field

from skiller.domain.agent.agent_llm_provider_model import AgentLLMProviderList
from skiller.domain.tool.tool_contract import ToolRuntimeConfigs


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
    llm: AgentLLMProviderList
    loop: AgentLoopConfig = field(default_factory=AgentLoopConfig)
    context: AgentContextConfig = field(default_factory=AgentContextConfig)
    event_output: AgentEventOutputConfig = field(default_factory=AgentEventOutputConfig)
    tools: ToolRuntimeConfigs = field(default_factory=ToolRuntimeConfigs)
