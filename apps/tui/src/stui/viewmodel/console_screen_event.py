from __future__ import annotations

from dataclasses import dataclass

from stui.usecase.run_event_context import RunMode, RunStatus


@dataclass(frozen=True)
class InspectRunContextEvent:
    run_id: str
    skill_name: str
    mode: RunMode
    status: RunStatus
    max_page: int
