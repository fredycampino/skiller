from dataclasses import dataclass


@dataclass(frozen=True)
class AgentContextObservedWindowStats:
    start_sequence: int
    end_sequence: int
    current_tokens: int


@dataclass(frozen=True)
class AgentContextObservedStats:
    entries: int
    estimated_tokens: int
    window: AgentContextObservedWindowStats


@dataclass(frozen=True)
class AgentContextWindowStats:
    start_sequence: int
    end_sequence: int
    current_tokens: int
    limit_tokens: int
    capacity_tokens: int


@dataclass(frozen=True)
class AgentContextStats:
    entries: int
    estimated_tokens: int
    window: AgentContextWindowStats


@dataclass(frozen=True)
class AgentStats:
    run_id: str
    agent_id: str
    context_id: str
    context: AgentContextStats
