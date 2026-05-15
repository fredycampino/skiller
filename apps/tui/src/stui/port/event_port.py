from __future__ import annotations

from typing import Protocol

from stui.port.event_models import LogEvent


class LogEventsListener(Protocol):
    def notify(self, events: list[LogEvent]) -> None: ...

    def get_max_page(self) -> int: ...


class LogEventsObserver(Protocol):
    def subscribe(self, *, run_id: str, listener: LogEventsListener) -> None: ...

    def unsubscribe(self) -> None: ...


class EventsPort(Protocol):
    def subscribe(self, *, run_id: str, listener: LogEventsListener) -> None: ...

    def unsubscribe(self) -> None: ...
