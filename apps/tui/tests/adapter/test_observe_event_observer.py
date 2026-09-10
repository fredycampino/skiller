from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

import pytest

from stui.adapter.events.cli_log_event import CliLogEvent
from stui.adapter.events.cli_observe_frame import (
    CliObserveEventFrame,
    CliObserveFrame,
    CliObserveStartFrame,
    CliObserveStopFrame,
    CliObserveWaitFrame,
)
from stui.adapter.events.observe_event_observer import ObserveEventObserver
from stui.port.event_models import ErrorPayload, LogEvent, LogEventType

pytestmark = pytest.mark.unit

EVENT_TIMEOUT_SECONDS = 1.0


@dataclass
class FakeObserveSource:
    streams: list[list[CliObserveFrame] | Exception]
    calls: list[tuple[str, int | None, int]] = field(default_factory=list)
    completed: asyncio.Event = field(default_factory=asyncio.Event)

    async def stream(
        self,
        *,
        run_id: str,
        after_sequence: int | None,
        tail: int,
    ) -> AsyncGenerator[CliObserveFrame, None]:
        self.calls.append((run_id, after_sequence, tail))
        result = self.streams.pop(0)
        try:
            if isinstance(result, Exception):
                raise result
            for frame in result:
                yield frame
        finally:
            if not self.streams:
                self.completed.set()


class FakeLogEventsListener:
    def __init__(self) -> None:
        self.events: list[LogEvent] = []
        self.notified = asyncio.Event()

    def notify(self, events: list[LogEvent]) -> None:
        self.events.extend(events)
        self.notified.set()

    def get_max_page(self) -> int:
        return 100


def test_observer_forwards_events_and_ignores_control_frames() -> None:
    async def run() -> None:
        source = FakeObserveSource(
            [
                [
                    _start(),
                    _event_frame(sequence=1),
                    CliObserveWaitFrame(kind="wait", sequence=1, wait_type="input"),
                    _event_frame(sequence=2, event_type=LogEventType.RUN_WAITING),
                    CliObserveStopFrame(kind="stop", sequence=2, status="succeeded"),
                ]
            ]
        )
        listener = FakeLogEventsListener()
        observer = ObserveEventObserver(source=source)

        observer.subscribe(
            run_id="run-1",
            listener=listener,
            after_sequence=None,
            tail=25,
        )
        await _wait_for(source.completed)

        assert source.calls == [("run-1", None, 25)]
        assert [event.sequence for event in listener.events] == [1, 2]

    asyncio.run(run())


def test_observer_reconnects_from_last_event_after_unexpected_eof() -> None:
    async def run() -> None:
        source = FakeObserveSource(
            [
                [_start(), _event_frame(sequence=1)],
                [
                    CliObserveStartFrame(
                        kind="start",
                        version=1,
                        run_id="run-1",
                        requested_after=1,
                        effective_after=1,
                        last_sequence=2,
                        tail=100,
                        truncated=False,
                    ),
                    _event_frame(sequence=2),
                    CliObserveStopFrame(kind="stop", sequence=2, status="succeeded"),
                ],
            ]
        )
        listener = FakeLogEventsListener()
        observer = ObserveEventObserver(source=source)

        observer.subscribe(
            run_id="run-1",
            listener=listener,
            after_sequence=None,
            tail=100,
        )
        await _wait_for(source.completed)

        assert source.calls == [("run-1", None, 100), ("run-1", 1, 100)]
        assert [event.sequence for event in listener.events] == [1, 2]

    asyncio.run(run())


def test_observer_stops_without_consuming_frames_after_stop() -> None:
    class StopThenFailsSource:
        def __init__(self) -> None:
            self.reached_after_stop = False
            self.closed = asyncio.Event()

        async def stream(
            self,
            *,
            run_id: str,
            after_sequence: int | None,
            tail: int,
        ) -> AsyncGenerator[CliObserveFrame, None]:
            _ = run_id, after_sequence, tail
            try:
                yield _start()
                yield CliObserveStopFrame(kind="stop", sequence=0, status="succeeded")
                self.reached_after_stop = True
                raise AssertionError("stream was consumed after stop")
            finally:
                self.closed.set()

    async def run() -> None:
        source = StopThenFailsSource()
        listener = FakeLogEventsListener()
        observer = ObserveEventObserver(source=source)
        observer.subscribe(
            run_id="run-1",
            listener=listener,
            after_sequence=None,
            tail=100,
        )
        await _wait_for(source.closed)

        assert not source.reached_after_stop
        assert source.closed.is_set()
        assert listener.events == []

    asyncio.run(run())


def test_observer_restarts_same_run_after_error() -> None:
    async def run() -> None:
        source = FakeObserveSource(
            [
                RuntimeError("boom"),
                [_start(), CliObserveStopFrame(kind="stop", sequence=0, status="succeeded")],
            ]
        )
        listener = FakeLogEventsListener()
        observer = ObserveEventObserver(source=source)
        observer.subscribe(
            run_id="run-1",
            listener=listener,
            after_sequence=None,
            tail=100,
        )
        await _wait_for(listener.notified)

        observer.subscribe(
            run_id="run-1",
            listener=listener,
            after_sequence=0,
            tail=100,
        )
        await _wait_for(source.completed)

        assert source.calls == [("run-1", None, 100), ("run-1", 0, 100)]

    asyncio.run(run())


def test_observer_reports_stream_errors_as_normalized_event() -> None:
    async def run() -> None:
        listener = FakeLogEventsListener()
        observer = ObserveEventObserver(source=FakeObserveSource([RuntimeError("boom")]))

        observer.subscribe(
            run_id="run-1",
            listener=listener,
            after_sequence=None,
            tail=100,
        )
        await _wait_for(listener.notified)

        assert len(listener.events) == 1
        error = listener.events[0]
        assert error.event_type == LogEventType.OBSERVER_LOOP_ERROR
        assert error.payload == ErrorPayload(error="RuntimeError: boom")

    asyncio.run(run())


def test_observer_discards_late_frames_after_subscribing_to_another_run() -> None:
    class SwitchingListener(FakeLogEventsListener):
        def __init__(self) -> None:
            super().__init__()
            self.observer: ObserveEventObserver | None = None

        def notify(self, events: list[LogEvent]) -> None:
            super().notify(events)
            if events[-1].run_id != "run-1":
                return
            assert self.observer is not None
            self.observer.subscribe(
                run_id="run-2",
                listener=self,
                after_sequence=None,
                tail=100,
            )

    async def run() -> None:
        source = FakeObserveSource(
            [
                [_start(), _event_frame(sequence=1), _event_frame(sequence=2)],
                [
                    CliObserveStartFrame(
                        kind="start",
                        version=1,
                        run_id="run-2",
                        requested_after=None,
                        effective_after=0,
                        last_sequence=1,
                        tail=100,
                        truncated=False,
                    ),
                    _event_frame(sequence=1, run_id="run-2"),
                    CliObserveStopFrame(kind="stop", sequence=1, status="succeeded"),
                ],
            ]
        )
        listener = SwitchingListener()
        observer = ObserveEventObserver(source=source)
        listener.observer = observer
        observer.subscribe(
            run_id="run-1",
            listener=listener,
            after_sequence=None,
            tail=100,
        )
        await _wait_for(source.completed)

        assert [(event.run_id, event.sequence) for event in listener.events] == [
            ("run-1", 1),
            ("run-2", 1),
        ]

    asyncio.run(run())


def test_unsubscribe_cancels_active_stream() -> None:
    class BlockingSource:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.cancelled = asyncio.Event()

        async def stream(
            self,
            *,
            run_id: str,
            after_sequence: int | None,
            tail: int,
        ) -> AsyncGenerator[CliObserveFrame, None]:
            _ = run_id, after_sequence, tail
            try:
                self.started.set()
                yield _start()
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled.set()
                raise

    async def run() -> None:
        source = BlockingSource()
        observer = ObserveEventObserver(source=source)
        observer.subscribe(
            run_id="run-1",
            listener=FakeLogEventsListener(),
            after_sequence=None,
            tail=100,
        )
        await _wait_for(source.started)

        observer.unsubscribe()
        await _wait_for(source.cancelled)

        assert source.cancelled.is_set()

    asyncio.run(run())


async def _wait_for(event: asyncio.Event) -> None:
    await asyncio.wait_for(event.wait(), timeout=EVENT_TIMEOUT_SECONDS)


def _start() -> CliObserveStartFrame:
    return CliObserveStartFrame(
        kind="start",
        version=1,
        run_id="run-1",
        requested_after=None,
        effective_after=0,
        last_sequence=2,
        tail=100,
        truncated=False,
    )


def _event_frame(
    *,
    sequence: int,
    event_type: LogEventType = LogEventType.STEP_STARTED,
    run_id: str = "run-1",
) -> CliObserveEventFrame:
    return CliObserveEventFrame(
        kind="event",
        event=CliLogEvent(
            sequence=sequence,
            id=f"evt-{sequence}",
            run_id=run_id,
            type=event_type,
            step_id="ask" if event_type == LogEventType.RUN_WAITING else "agent",
            step_type="wait_input" if event_type == LogEventType.RUN_WAITING else "agent",
            agent_sequence=None,
            created_at="2026-05-12T10:30:15Z",
            payload=(
                {
                    "output": {
                        "text": "Continue?",
                        "value": {"prompt": "Continue?", "payload": None},
                        "body_ref": None,
                    }
                }
                if event_type == LogEventType.RUN_WAITING
                else {}
            ),
        ),
    )
