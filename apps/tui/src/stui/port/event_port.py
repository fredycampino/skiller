from __future__ import annotations

from typing import Protocol

from stui.port.event_models import LogEvent

DEFAULT_POLL_INTERVAL_SECONDS = 0.5


class LogEventsListener(Protocol):
    def notify(self, events: list[LogEvent]) -> None: ...

    def get_max_page(self) -> int: ...


class LogEventsObserver(Protocol):
    def subscribe(
        self,
        *,
        run_id: str,
        listener: LogEventsListener,
        after_sequence: int,
        interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> None: ...

    def unsubscribe(self) -> None: ...


class EventsPort(Protocol):
    def subscribe(
        self,
        *,
        run_id: str,
        listener: LogEventsListener,
        interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> None: ...

    def unsubscribe(self) -> None: ...
