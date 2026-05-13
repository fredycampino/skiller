from __future__ import annotations

from typing import Protocol

from stui.port.event_models import LogEvent


class LogEventsListener(Protocol):
    def notify(self, events: list[LogEvent]) -> None: ...


class LogEventsObserverPort(Protocol):
    def subscribe(self, *, run_id: str, listener: LogEventsListener) -> None: ...

    def unsubscribe(self) -> None: ...
