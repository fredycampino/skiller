from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RunListItem:
    id: str
    skill_source: str
    skill_ref: str
    status: str
    current: str | None
    created_at: str
    updated_at: str
    wait_type: str | None = None
    wait_detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "skill_source": self.skill_source,
            "skill_ref": self.skill_ref,
            "status": self.status,
            "current": self.current,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.wait_type:
            payload["wait_type"] = self.wait_type
        if self.wait_detail:
            payload["wait_detail"] = self.wait_detail
        return payload
