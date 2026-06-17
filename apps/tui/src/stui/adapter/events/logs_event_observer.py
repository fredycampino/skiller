from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from stui.adapter.events.cli_log_event import CliLogEvent
from stui.adapter.events.cli_log_event_adapter import CliLogEventAdapter
from stui.adapter.events.log_event_mapper import LogEventMapper
from stui.port.event_models import ErrorPayload, LogEvent, LogEventType
from stui.port.event_port import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    LogEventsListener,
    LogEventsObserver,
)


class CliLogEventSource(Protocol):
    def list(
        self,
        run_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[CliLogEvent]: ...


@dataclass
class LogsEventObserver(LogEventsObserver):
    logs: CliLogEventSource = field(default_factory=CliLogEventAdapter)
    mapper: LogEventMapper = field(default_factory=LogEventMapper)
    _listener: LogEventsListener | None = field(default=None, init=False, repr=False)
    _run_id: str = field(default="", init=False, repr=False)
    _task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)
    _last_seen_sequence: int = field(default=0, init=False, repr=False)
    _pending_stop: bool = field(default=False, init=False, repr=False)
    _observer_error_count: int = field(default=0, init=False, repr=False)
    _current_interval_seconds: float = field(
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        init=False,
        repr=False,
    )

    def subscribe(
        self,
        *,
        run_id: str,
        listener: LogEventsListener,
        after_sequence: int,
        interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> None:
        normalized_run_id = run_id.strip()
        if not normalized_run_id:
            raise RuntimeError("log observer requires run_id")

        if (
            self._run_id == normalized_run_id
            and self._listener is listener
            and self._task is asyncio.current_task()
        ):
            self._current_interval_seconds = interval_seconds
            self._pending_stop = False
            return

        last_seen_sequence = self._last_seen_sequence
        if self._run_id != normalized_run_id:
            last_seen_sequence = after_sequence
            self._observer_error_count = 0
        self._stop_current()
        self._run_id = normalized_run_id
        self._listener = listener
        self._last_seen_sequence = last_seen_sequence
        self._pending_stop = False
        self._current_interval_seconds = interval_seconds
        self._task = asyncio.create_task(self._poll_loop(listener))

    def unsubscribe(self) -> None:
        self._stop_current()
        self._run_id = ""
        self._last_seen_sequence = 0
        self._pending_stop = False
        self._observer_error_count = 0

    def _stop_current(self) -> None:
        self._listener = None
        self._pending_stop = False
        if self._task is None or self._task.done():
            self._task = None
            return

        self._task.cancel()
        self._task = None

    async def _poll_loop(self, listener: LogEventsListener) -> None:
        try:
            while self._listener is listener:
                events = await asyncio.to_thread(self._list_next_events, listener)
                if not events and self._pending_stop:
                    self._listener = None
                    self._pending_stop = False
                    return
                if not events:
                    await asyncio.sleep(self._current_interval_seconds)
                    continue

                self._last_seen_sequence = max(event.sequence for event in events)
                if _ends_in_finished(events):
                    listener.notify(events)
                    self._listener = None
                    return

                self._pending_stop = _ends_in_waiting(events)
                listener.notify(events)
                await asyncio.sleep(self._current_interval_seconds)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._notify_error(exc)
            raise
        finally:
            self._task = None

    def _list_next_events(self, listener: LogEventsListener) -> list[LogEvent]:
        events = self.logs.list(
            self._run_id,
            after_sequence=self._last_seen_sequence or None,
            limit=listener.get_max_page(),
        )
        return [self.mapper.map(event) for event in events]

    def _notify_error(self, exc: Exception) -> None:
        listener = self._listener
        if listener is None or not self._run_id:
            return

        self._observer_error_count += 1
        listener.notify(
            [
                LogEvent(
                    sequence=self._last_seen_sequence,
                    event_id=(
                        f"observer-loop-error:{self._run_id}:{self._observer_error_count}"
                    ),
                    run_id=self._run_id,
                    event_type=LogEventType.OBSERVER_LOOP_ERROR,
                    step_id=None,
                    step_type=None,
                    agent_sequence=None,
                    created_at=datetime.now(UTC).isoformat(),
                    payload=ErrorPayload(error=self._observer_error_message(exc)),
                )
            ]
        )

    def _observer_error_message(self, exc: Exception) -> str:
        return f"{type(exc).__name__}: {str(exc).strip() or 'observer error'}"


def _ends_in_finished(events: list[LogEvent]) -> bool:
    if not events:
        return False
    return events[-1].event_type == LogEventType.RUN_FINISHED


def _ends_in_waiting(events: list[LogEvent]) -> bool:
    if not events:
        return False
    return events[-1].event_type == LogEventType.RUN_WAITING
