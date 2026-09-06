from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from skiller.domain.run.run_context_model import RunContext


class RunStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class RunAgent:
    agent_id: str
    context_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "context_id": self.context_id,
        }


@dataclass(frozen=True)
class RunSnapshotSyncState:
    run_id: str
    flow_path: Path
    current: str | None
    snapshot: dict[str, Any]


@dataclass
class Run:
    id: str
    flow_path: Path
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
            "flow_path": str(self.flow_path),
            "snapshot": self.snapshot,
            "agents": {agent_id: agent.to_dict() for agent_id, agent in self.agents.items()},
            "status": self.status,
            "current": self.current,
            "context": self.context.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
