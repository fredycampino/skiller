from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from stui.adapter.events.cli_log_event import CliLogEvent
from stui.adapter.events.cli_log_event_adapter import CliLogEventAdapter
from stui.adapter.events.log_event_mapper import LogEventMapper
from stui.port.event_models import ErrorPayload, LogEvent, LogEventType
from stui.port.event_port import LogEventsListener
from stui.port.run_port import RunPort, RunRuntimeStatus

_STOP_EVENT_TYPES = {
    LogEventType.RUN_WAITING,
    LogEventType.RUN_FINISHED,
}


class CliLogEventSource(Protocol):
    def list(
        self,
        run_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[CliLogEvent]: ...


@dataclass
class LogsEventObserver:
    interval_seconds: float = 0.5
    limit: int = 100
    logs: CliLogEventSource = field(default_factory=CliLogEventAdapter)
    mapper: LogEventMapper = field(default_factory=LogEventMapper)
    run_port: RunPort | None = None
    _listener: LogEventsListener | None = field(default=None, init=False, repr=False)
    _run_id: str = field(default="", init=False, repr=False)
    _task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)
    _last_seen_sequence: int = field(default=0, init=False, repr=False)
    _pending_stop: bool = field(default=False, init=False, repr=False)
    _observer_error_count: int = field(default=0, init=False, repr=False)

    def subscribe(self, *, run_id: str, listener: LogEventsListener) -> None:
        normalized_run_id = run_id.strip()
        if not normalized_run_id:
            raise RuntimeError("log observer requires run_id")

        last_seen_sequence = self._last_seen_sequence
        if self._run_id != normalized_run_id:
            last_seen_sequence = 0
            self._observer_error_count = 0
        self._stop_current()
        self._run_id = normalized_run_id
        self._listener = listener
        self._last_seen_sequence = last_seen_sequence
        self._pending_stop = False
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
                events = await asyncio.to_thread(self._list_next_events)
                if events:
                    listener.notify(events)
                    self._last_seen_sequence = max(event.sequence for event in events)
                    self._pending_stop = _ends_in_stop(events)
                elif self._pending_stop:
                    self._listener = None
                    self._pending_stop = False
                    return
                await asyncio.sleep(self.interval_seconds)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._notify_error(exc)
            raise
        finally:
            self._task = None

    def _list_next_events(self) -> list[LogEvent]:
        events = self.logs.list(
            self._run_id,
            after_sequence=self._last_seen_sequence or None,
            limit=self.limit,
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
        message = f"{type(exc).__name__}: {str(exc).strip() or 'observer error'}"
        status = self._current_run_status()
        if status is None:
            return message
        return (
            f"{message} "
            f"(run_status={status.status.value}, "
            f"wait_type={status.wait_type.value}, "
            f"last_event_sequence={status.last_event_sequence}, "
            f"last_event_type={status.last_event_type or '-'})"
        )

    def _current_run_status(self) -> RunRuntimeStatus | None:
        if self.run_port is None or not self._run_id:
            return None
        try:
            return self.run_port.status(self._run_id)
        except Exception:
            return None


def _ends_in_stop(events: list[LogEvent]) -> bool:
    if not events:
        return False
    return events[-1].event_type in _STOP_EVENT_TYPES
