from __future__ import annotations

from dataclasses import dataclass

from stui.port.event_port import EventsPort


@dataclass(frozen=True)
class RefreshEventsUseCase:
    events_port: EventsPort

    async def execute(self) -> None:
        await self.events_port.refresh()
