from __future__ import annotations

from dataclasses import dataclass

from stui.port.event_models import LogEvent
from stui.usecase.run_event_context import RunEventContext


@dataclass(frozen=True)
class AgentStatusUseCase:
    def execute(
        self,
        *,
        context: RunEventContext,
        events: list[LogEvent],
    ) -> None:
        for event in sorted(
            events,
            key=lambda event: (event.created_at, event.sequence),
            reverse=True,
        ):
            if event.step_type != "agent":
                continue
            if event.step_id is None:
                continue
            context.agent_id = event.step_id
            return
