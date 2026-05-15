from __future__ import annotations

from dataclasses import dataclass, field

from stui.port.event_models import LogEvent
from stui.port.event_port import EventsPort, LogEventsListener, LogEventsObserver

DEFAULT_MAX_EVENTS_WINDOW = 10


@dataclass
class _ActiveSubscription:
    listener: LogEventsListener
    run_id: str
    events: list[LogEvent] = field(default_factory=list)


@dataclass
class DefaultEventsPort(EventsPort, LogEventsListener):
    event_observer: LogEventsObserver
    _subscription: _ActiveSubscription | None = field(default=None, init=False, repr=False)

    def subscribe(self, *, run_id: str, listener: LogEventsListener) -> None:
        normalized_run_id = run_id.strip()
        if not normalized_run_id:
            raise RuntimeError("events port requires run_id")
        subscription = self._subscription
        if subscription is None or subscription.run_id != normalized_run_id:
            self._subscription = _ActiveSubscription(
                listener=listener,
                run_id=normalized_run_id,
            )
        else:
            subscription.listener = listener
        self.event_observer.subscribe(run_id=normalized_run_id, listener=self)

    def unsubscribe(self) -> None:
        self.event_observer.unsubscribe()
        self._subscription = None

    def notify(self, events: list[LogEvent]) -> None:
        subscription = self._subscription
        if subscription is None:
            return
        seen_sequences = {event.sequence for event in subscription.events}

        for event in events:
            if event.sequence in seen_sequences:
                continue
            subscription.events.append(event)
            seen_sequences.add(event.sequence)

        self._trim_window(subscription, max_events=subscription.listener.get_max_page())
        subscription.listener.notify(list(subscription.events))

    def get_max_page(self) -> int:
        subscription = self._subscription
        if subscription is None:
            return DEFAULT_MAX_EVENTS_WINDOW
        return subscription.listener.get_max_page()

    def _trim_window(self, subscription: _ActiveSubscription, *, max_events: int) -> None:
        overflow = len(subscription.events) - max_events
        if overflow <= 0:
            return
        del subscription.events[:overflow]
