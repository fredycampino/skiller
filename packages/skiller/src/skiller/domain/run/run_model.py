from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from skiller.domain.run.run_context_model import RunContext


class RunStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SkillSource(str, Enum):
    INTERNAL = "internal"
    FILE = "file"


@dataclass
class RunAgent:
    agent_id: str
    context_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "context_id": self.context_id,
        }


@dataclass
class Run:
    id: str
    source: str
    ref: str
    snapshot: dict[str, Any]
    status: str
    current: str | None
    context: RunContext
    created_at: str
    updated_at: str
    agents: dict[str, RunAgent] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "ref": self.ref,
            "snapshot": self.snapshot,
            "agents": {
                agent_id: agent.to_dict()
                for agent_id, agent in self.agents.items()
            },
            "status": self.status,
            "current": self.current,
            "context": self.context.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
