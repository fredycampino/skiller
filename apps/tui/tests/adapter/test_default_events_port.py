from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from stui.adapter.default_events_port import DEFAULT_MAX_EVENTS_WINDOW, DefaultEventsPort
from stui.port.event_models import InputReceivedPayload, LogEvent, LogEventType
from stui.port.event_port import DEFAULT_POLL_INTERVAL_SECONDS, LogEventsListener
from stui.port.run_port import RunRuntimeStatus, RunRuntimeStatusKind

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
    subscribe_calls: list[tuple[str, LogEventsListener]] = field(default_factory=list)
    subscribe_after_sequence_calls: list[int] = field(default_factory=list)
    subscribe_interval_calls: list[float] = field(default_factory=list)
    unsubscribe_calls: int = 0

    def subscribe(
        self,
        *,
        run_id: str,
        listener: LogEventsListener,
        after_sequence: int,
        interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> None:
        self.subscribe_calls.append((run_id, listener))
        self.subscribe_after_sequence_calls.append(after_sequence)
        self.subscribe_interval_calls.append(interval_seconds)

    def unsubscribe(self) -> None:
        self.unsubscribe_calls += 1


@dataclass
class FakeRunAdapter:
    status_value: RunRuntimeStatus | None = field(default_factory=lambda: _status())
    status_calls: list[str] = field(default_factory=list)

    def status(self, run_id: str) -> RunRuntimeStatus | None:
        self.status_calls.append(run_id)
        return self.status_value


def test_subscribe_requires_run_id() -> None:
    port = _port()
    listener = FakeLogEventsListener()

    with pytest.raises(RuntimeError, match="events port requires run_id"):
        port.subscribe(run_id=" ", listener=listener)


def test_subscribe_requires_existing_run_status() -> None:
    run_adapter = FakeRunAdapter(status_value=None)
    port = DefaultEventsPort(
        event_observer=FakeLogEventsObserver(),
        run_adapter=run_adapter,
    )
    listener = FakeLogEventsListener()

    with pytest.raises(RuntimeError, match="run 'run-1' not found"):
        port.subscribe(run_id="run-1", listener=listener)

    assert run_adapter.status_calls == ["run-1"]


def test_subscribe_uses_self_as_observer_listener() -> None:
    observer = FakeLogEventsObserver()
    listener = FakeLogEventsListener(max_page=25)
    run_adapter = FakeRunAdapter()
    port = DefaultEventsPort(event_observer=observer, run_adapter=run_adapter)

    port.subscribe(run_id=" run-1 ", listener=listener)

    assert run_adapter.status_calls == ["run-1"]
    assert observer.subscribe_calls == [("run-1", port)]
    assert observer.subscribe_after_sequence_calls == [0]
    assert observer.subscribe_interval_calls == [DEFAULT_POLL_INTERVAL_SECONDS]
    assert port.get_max_page() == 25


def test_subscribe_forwards_poll_interval() -> None:
    observer = FakeLogEventsObserver()
    listener = FakeLogEventsListener(max_page=25)
    port = _port(event_observer=observer)

    port.subscribe(run_id="run-1", listener=listener, interval_seconds=1.0)

    assert observer.subscribe_calls == [("run-1", port)]
    assert observer.subscribe_interval_calls == [1.0]


def test_subscribe_forwards_recent_event_window() -> None:
    observer = FakeLogEventsObserver()
    listener = FakeLogEventsListener(max_page=100)
    port = _port(
        event_observer=observer,
        status=_status(last_event_sequence=5000),
    )

    port.subscribe(run_id="run-1", listener=listener)

    assert observer.subscribe_after_sequence_calls == [4900]


def test_subscribe_uses_zero_when_status_has_no_event_sequence() -> None:
    observer = FakeLogEventsObserver()
    listener = FakeLogEventsListener(max_page=100)
    port = _port(
        event_observer=observer,
        status=_status(last_event_sequence=None),
    )

    port.subscribe(run_id="run-1", listener=listener)

    assert observer.subscribe_after_sequence_calls == [0]


def test_notify_without_subscription_is_ignored() -> None:
    observer = FakeLogEventsObserver()
    port = _port(event_observer=observer)

    port.notify([_event(sequence=1)])

    assert observer.subscribe_calls == []


def test_notify_sends_clean_window_to_listener() -> None:
    listener = FakeLogEventsListener()
    port = _port()
    port.subscribe(run_id="run-1", listener=listener)

    port.notify([_event(sequence=1)])
    port.notify([_event(sequence=2)])

    assert [[event.sequence for event in events] for events in listener.notifications] == [
        [1],
        [1, 2],
    ]


def test_notify_keeps_received_events() -> None:
    listener = FakeLogEventsListener()
    port = _port()
    port.subscribe(run_id="run-1", listener=listener)

    port.notify([_event(sequence=1)])
    port.notify([_event(sequence=1), _event(sequence=2)])

    assert [event.sequence for event in listener.notifications[-1]] == [1, 1, 2]


def test_notify_trims_window_with_listener_max_page() -> None:
    listener = FakeLogEventsListener(max_page=3)
    port = _port()
    port.subscribe(run_id="run-1", listener=listener)

    port.notify([_event(sequence=1), _event(sequence=2), _event(sequence=3), _event(sequence=4)])

    assert [event.sequence for event in listener.notifications[-1]] == [2, 3, 4]


def test_subscribe_same_run_keeps_window_and_updates_listener() -> None:
    old_listener = FakeLogEventsListener()
    new_listener = FakeLogEventsListener()
    port = _port()
    port.subscribe(run_id="run-1", listener=old_listener)
    port.notify([_event(sequence=1)])

    port.subscribe(run_id="run-1", listener=new_listener)
    port.notify([_event(sequence=2)])

    assert old_listener.notifications == [[_event(sequence=1)]]
    assert [event.sequence for event in new_listener.notifications[-1]] == [1, 2]


def test_subscribe_new_run_resets_window() -> None:
    listener = FakeLogEventsListener()
    port = _port()
    port.subscribe(run_id="run-1", listener=listener)
    port.notify([_event(sequence=1, run_id="run-1")])

    port.subscribe(run_id="run-2", listener=listener)
    port.notify([_event(sequence=1, run_id="run-2")])

    assert [event.run_id for event in listener.notifications[-1]] == ["run-2"]


def test_unsubscribe_clears_subscription() -> None:
    observer = FakeLogEventsObserver()
    listener = FakeLogEventsListener()
    port = _port(event_observer=observer)
    port.subscribe(run_id="run-1", listener=listener)

    port.unsubscribe()

    assert observer.unsubscribe_calls == 1
    assert port.get_max_page() == DEFAULT_MAX_EVENTS_WINDOW


def _port(
    *,
    event_observer: FakeLogEventsObserver | None = None,
    status: RunRuntimeStatus | None = None,
) -> DefaultEventsPort:
    return DefaultEventsPort(
        event_observer=event_observer or FakeLogEventsObserver(),
        run_adapter=FakeRunAdapter(status_value=status or _status()),
    )


def _status(*, last_event_sequence: int | None = 0) -> RunRuntimeStatus:
    return RunRuntimeStatus(
        run_id="run-1",
        status=RunRuntimeStatusKind.RUNNING,
        last_event_sequence=last_event_sequence,
    )


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
