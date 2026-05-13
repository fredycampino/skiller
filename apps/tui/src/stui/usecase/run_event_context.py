from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class RunStatus(StrEnum):
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    WAITING_WEBHOOK = "waiting_webhook"
    WAITING_CHANNEL = "waiting_channel"
    FAILED = "failed"
    SUCCESS = "success"


class RunMode(StrEnum):
    FLOW = "flow"
    CHAT = "chat"


@dataclass
class RunEventContext:
    run_id: str
    skill_name: str
    mode: RunMode
    status: RunStatus
    event_ids: set[str] = field(default_factory=set, init=False)

    def activate_run(
        self,
        run_id: str,
        *,
        skill_name: str,
        mode: RunMode,
        status: RunStatus,
    ) -> None:
        if self.run_id != run_id:
            self.event_ids.clear()
        self.run_id = run_id
        self.skill_name = skill_name
        self.mode = mode
        self.status = status

    def remember_event_id(self, event_id: str) -> bool:
        if not event_id:
            return False
        if event_id in self.event_ids:
            return True
        self.event_ids.add(event_id)
        return False
