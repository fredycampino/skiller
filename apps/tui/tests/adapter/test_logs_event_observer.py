from __future__ import annotations

import asyncio

import pytest

from stui.adapter.events.cli_log_event import CliLogEvent
from stui.adapter.events.logs_event_observer import LogsEventObserver
from stui.port.event_models import (
    ErrorPayload,
    LogEvent,
    LogEventType,
)
from stui.port.run_port import (
    RunRuntimeStatus,
    RunRuntimeStatusKind,
    RunRuntimeWaitType,
)

pytestmark = pytest.mark.unit


class FakeLogEventAdapter:
    def __init__(self, batches: list[list[CliLogEvent]]) -> None:
        self.batches = list(batches)
        self.called_with: list[tuple[str, int | None, int | None]] = []

    def list(
        self,
        run_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[CliLogEvent]:
        self.called_with.append((run_id, after_sequence, limit))
        return self.batches.pop(0) if self.batches else []


class FakeLogEventsListener:
    def __init__(self, *, max_page: int = 100) -> None:
        self.events: list[LogEvent] = []
        self.max_page = max_page

    def notify(self, events: list[LogEvent]) -> None:
        self.events.extend(events)

    def get_max_page(self) -> int:
        return self.max_page


class FakeRunPort:
    def __init__(self, *, status: RunRuntimeStatus | None) -> None:
        self.status_value = status

    def status(self, _run_id: str) -> RunRuntimeStatus | None:
        return self.status_value


def test_logs_event_observer_polls_incrementally_and_stops_on_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_sleep = asyncio.sleep
    adapter = FakeLogEventAdapter(
        [
            [_step_started_event(sequence=1)],
            [_run_waiting_event(sequence=2)],
        ]
    )
    listener = FakeLogEventsListener()

    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return function(*args, **kwargs)

    async def fake_sleep(_seconds: float) -> None:
        await original_sleep(0)

    async def run() -> None:
        monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)
        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        observer = LogsEventObserver(interval_seconds=0.0, logs=adapter)
        observer.subscribe(run_id="run-1", listener=listener)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert [event.sequence for event in listener.events] == [1, 2]
        assert adapter.called_with == [
            ("run-1", None, 100),
            ("run-1", 1, 100),
            ("run-1", 2, 100),
        ]

    asyncio.run(run())


def test_logs_event_observer_uses_listener_max_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_sleep = asyncio.sleep
    adapter = FakeLogEventAdapter([[_step_started_event(sequence=1)]])
    listener = FakeLogEventsListener(max_page=25)

    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return function(*args, **kwargs)

    async def fake_sleep(_seconds: float) -> None:
        await original_sleep(0)

    async def run() -> None:
        monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)
        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        observer = LogsEventObserver(interval_seconds=0.0, logs=adapter)
        observer.subscribe(run_id="run-1", listener=listener)
        await asyncio.sleep(0)

        assert adapter.called_with[0] == ("run-1", None, 25)

    asyncio.run(run())


def test_logs_event_observer_keeps_cursor_when_resubscribing_same_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_sleep = asyncio.sleep
    adapter = FakeLogEventAdapter(
        [
            [_run_waiting_event(sequence=3)],
            [_step_started_event(sequence=4), _run_waiting_event(sequence=5)],
        ]
    )
    listener = FakeLogEventsListener()

    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return function(*args, **kwargs)

    async def fake_sleep(_seconds: float) -> None:
        await original_sleep(0)

    async def run() -> None:
        monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)
        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        observer = LogsEventObserver(interval_seconds=0.0, logs=adapter)

        observer.subscribe(run_id="run-1", listener=listener)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        observer.subscribe(run_id="run-1", listener=listener)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert [event.sequence for event in listener.events] == [3, 4, 5]
        assert adapter.called_with[0] == ("run-1", None, 100)
        assert ("run-1", 3, 100) in adapter.called_with
        assert adapter.called_with[-1] == ("run-1", 5, 100)

    asyncio.run(run())


def test_logs_event_observer_does_not_stop_on_historical_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_sleep = asyncio.sleep
    adapter = FakeLogEventAdapter(
        [
            [_run_waiting_event(sequence=2)],
            [_step_started_event(sequence=3), _run_waiting_event(sequence=4)],
            [],
        ]
    )
    listener = FakeLogEventsListener()

    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return function(*args, **kwargs)

    async def fake_sleep(_seconds: float) -> None:
        await original_sleep(0)

    async def run() -> None:
        monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)
        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        observer = LogsEventObserver(interval_seconds=0.0, logs=adapter)

        observer.subscribe(run_id="run-1", listener=listener)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert [event.sequence for event in listener.events] == [2, 3, 4]
        assert adapter.called_with == [
            ("run-1", None, 100),
            ("run-1", 2, 100),
            ("run-1", 4, 100),
        ]

    asyncio.run(run())


def test_logs_event_observer_notifies_observer_loop_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return function(*args, **kwargs)

    async def run() -> None:
        monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)
        adapter = FailingLogEventAdapter()
        listener = FakeLogEventsListener()
        observer = LogsEventObserver(
            interval_seconds=0.0,
            logs=adapter,
            run_port=FakeRunPort(
                status=RunRuntimeStatus(
                    run_id="run-1",
                    status=RunRuntimeStatusKind.WAITING,
                    wait_type=RunRuntimeWaitType.INPUT,
                    last_event_sequence=71,
                    last_event_type="RUN_WAITING",
                )
            ),
        )

        observer.subscribe(run_id="run-1", listener=listener)
        task = observer._task
        assert task is not None

        with pytest.raises(RuntimeError, match="boom"):
            await task

        assert len(listener.events) == 1
        event = listener.events[0]
        assert event.event_type == LogEventType.OBSERVER_LOOP_ERROR
        assert isinstance(event.payload, ErrorPayload)
        assert event.payload.error == (
            "RuntimeError: boom "
            "(run_status=waiting, wait_type=input, "
            "last_event_sequence=71, last_event_type=RUN_WAITING)"
        )

    asyncio.run(run())


def _step_started_event(*, sequence: int) -> CliLogEvent:
    return CliLogEvent(
        sequence=sequence,
        id=f"evt-{sequence}",
        run_id="run-1",
        type=LogEventType.STEP_STARTED,
        step_id="answer",
        step_type="llm_prompt",
        agent_sequence=None,
        created_at="2026-05-12T10:30:12Z",
        payload={},
    )


def _run_waiting_event(*, sequence: int) -> CliLogEvent:
    return CliLogEvent(
        sequence=sequence,
        id=f"evt-{sequence}",
        run_id="run-1",
        type=LogEventType.RUN_WAITING,
        step_id="ask_user",
        step_type="wait_input",
        agent_sequence=None,
        created_at="2026-05-12T10:30:17Z",
        payload={
            "output": {
                "text": "Write a message.",
                "value": {"prompt": "Write a message.", "payload": None},
                "body_ref": None,
            }
        },
    )


class FailingLogEventAdapter:
    def list(
        self,
        run_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[CliLogEvent]:
        raise RuntimeError("boom")
