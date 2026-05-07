from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class RunMode(StrEnum):
    FLOW = "flow"
    AGENT = "agent"


class RunStatus(StrEnum):
    RUNNING = "running"
    WAITING = "waiting"
    WAITING_INPUT = "waiting_input"
    FAILED = "failed"
    SUCCESS = "success"


@dataclass
class RunEventContext:
    run_id: str = ""
    skill_name: str = ""
    mode: RunMode = RunMode.FLOW
    status: RunStatus | None = None
    event_ids: set[str] = field(default_factory=set)

    def activate_run(
        self,
        run_id: str,
        *,
        skill_name: str = "",
        mode: RunMode | None = None,
        status: RunStatus | None = None,
    ) -> None:
        normalized_run_id = run_id.strip()
        if self.run_id != normalized_run_id:
            self.event_ids.clear()
        self.run_id = normalized_run_id
        if skill_name:
            self.skill_name = skill_name
        elif not normalized_run_id:
            self.skill_name = ""
        if mode is not None:
            self.mode = mode
        self.status = status

    def remember_event_id(self, event_id: str) -> bool:
        normalized_event_id = event_id.strip()
        if not normalized_event_id:
            return False
        if normalized_event_id in self.event_ids:
            return True
        self.event_ids.add(normalized_event_id)
        return False
