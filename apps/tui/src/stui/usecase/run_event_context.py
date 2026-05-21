from __future__ import annotations

from dataclasses import dataclass
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
    max_page: int = 100

    def activate_run(
        self,
        run_id: str,
        *,
        skill_name: str,
        status: RunStatus,
    ) -> None:
        self.run_id = run_id
        self.skill_name = skill_name
        self.status = status
