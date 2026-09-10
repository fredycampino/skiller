from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from stui.adapter.default_events_port import DEFAULT_MAX_EVENTS_WINDOW, DefaultEventsPort
from stui.port.event_models import InputReceivedPayload, LogEvent, LogEventType
from stui.port.event_port import LogEventsListener

pytestmark = pytest.mark.unit


@dataclass
class FakeLogEventsListener(LogEventsListener):
    max_page: int = 10
    notifications: list[list[LogEvent]] = field(default_factory=list)

    def notify(self, events: list[LogEvent]) -> None:
        self.notifications.append(list(events))

    def get_max_page(self) -> int:
        return self.max_page


@dataclass
class FakeLogEventsObserver:
    subscribe_calls: list[tuple[str, LogEventsListener, int | None, int]] = field(
        default_factory=list
    )
    unsubscribe_calls: int = 0

    def subscribe(
        self,
        *,
        run_id: str,
        listener: LogEventsListener,
        after_sequence: int | None,
        tail: int,
    ) -> None:
        self.subscribe_calls.append((run_id, listener, after_sequence, tail))

    def unsubscribe(self) -> None:
        self.unsubscribe_calls += 1


def test_subscribe_requires_run_id() -> None:
    port = _port()

    with pytest.raises(RuntimeError, match="events port requires run_id"):
        port.subscribe(run_id=" ", listener=FakeLogEventsListener())


def test_subscribe_starts_observe_with_initial_tail() -> None:
    observer = FakeLogEventsObserver()
    port = _port(event_observer=observer)
    listener = FakeLogEventsListener(max_page=25)

    port.subscribe(run_id=" run-1 ", listener=listener)

    assert observer.subscribe_calls == [("run-1", port, None, 25)]


def test_subscribe_same_run_reuses_cursor_and_updates_listener() -> None:
    observer = FakeLogEventsObserver()
    port = _port(event_observer=observer)
    old_listener = FakeLogEventsListener()
    new_listener = FakeLogEventsListener()
    port.subscribe(run_id="run-1", listener=old_listener)
    port.notify([_event(sequence=1)])

    port.subscribe(run_id="run-1", listener=new_listener)
    port.notify([_event(sequence=2)])

    assert observer.subscribe_calls == [
        ("run-1", port, None, 10),
        ("run-1", port, 1, 10),
    ]
    assert old_listener.notifications == [[_event(sequence=1)]]
    assert [event.sequence for event in new_listener.notifications[-1]] == [1, 2]


def test_subscribe_new_run_replaces_visible_window() -> None:
    observer = FakeLogEventsObserver()
    port = _port(event_observer=observer)
    listener = FakeLogEventsListener()
    port.subscribe(run_id="run-1", listener=listener)
    port.notify([_event(sequence=1, run_id="run-1")])

    port.subscribe(run_id="run-2", listener=listener)
    port.notify([_event(sequence=1, run_id="run-2")])

    assert [call[0] for call in observer.subscribe_calls] == ["run-1", "run-2"]
    assert [event.run_id for event in listener.notifications[-1]] == ["run-2"]


def test_notify_trims_window_with_listener_max_page() -> None:
    listener = FakeLogEventsListener(max_page=3)
    port = _port()
    port.subscribe(run_id="run-1", listener=listener)

    port.notify([_event(sequence=1), _event(sequence=2), _event(sequence=3), _event(sequence=4)])

    assert [event.sequence for event in listener.notifications[-1]] == [2, 3, 4]


def test_unsubscribe_discards_late_events() -> None:
    observer = FakeLogEventsObserver()
    port = _port(event_observer=observer)
    listener = FakeLogEventsListener()
    port.subscribe(run_id="run-1", listener=listener)

    port.unsubscribe()
    port.notify([_event(sequence=1)])

    assert observer.unsubscribe_calls == 1
    assert port.get_max_page() == DEFAULT_MAX_EVENTS_WINDOW
    assert listener.notifications == []


def _port(*, event_observer: FakeLogEventsObserver | None = None) -> DefaultEventsPort:
    return DefaultEventsPort(event_observer=event_observer or FakeLogEventsObserver())


def _event(*, sequence: int, run_id: str = "run-1") -> LogEvent:
    return LogEvent(
        sequence=sequence,
        event_id=f"evt-{sequence}",
        run_id=run_id,
        event_type=LogEventType.INPUT_RECEIVED,
        step_id=None,
        step_type=None,
        agent_sequence=None,
        created_at="2026-05-14T10:00:00Z",
        payload=InputReceivedPayload(payload={"text": f"message-{sequence}"}),
    )
