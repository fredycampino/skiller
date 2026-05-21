from dataclasses import dataclass


@dataclass(frozen=True)
class AgentRun:
    run_id: str
    agent_id: str


@dataclass(frozen=True)
class AgentContext:
    run_id: str
    agent_id: str
    context_id: str
