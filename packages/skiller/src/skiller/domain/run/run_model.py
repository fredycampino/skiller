from dataclasses import dataclass
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
class Run:
    id: str
    skill_source: str
    skill_ref: str
    skill_snapshot: dict[str, Any]
    status: str
    current: str | None
    context: RunContext
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "skill_source": self.skill_source,
            "skill_ref": self.skill_ref,
            "status": self.status,
            "current": self.current,
            "context": self.context.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
