from dataclasses import dataclass


@dataclass(frozen=True)
class AgentContextEntryStats:
    total: int
    user_messages: int
    assistant_messages: int
    tool_calls: int
    tool_results: int


@dataclass(frozen=True)
class AgentContextUsageStats:
    entries: int
    total_prompt_tokens: int
    total_response_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class AgentContextStats:
    entries: AgentContextEntryStats
    usage: AgentContextUsageStats


@dataclass(frozen=True)
class AgentStats:
    run_id: str
    agent_id: str
    context_id: str
    context: AgentContextStats
