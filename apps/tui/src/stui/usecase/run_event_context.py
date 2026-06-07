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
    run_name: str
    mode: RunMode
    status: RunStatus
    max_page: int = 100
    agent_id: str = ""
    actions_done: set[str] = field(default_factory=set)

    def activate_run(
        self,
        run_id: str,
        *,
        run_name: str,
        status: RunStatus,
    ) -> None:
        self.run_id = run_id
        self.run_name = run_name
        self.status = status
        self.agent_id = ""
        self.actions_done.clear()
