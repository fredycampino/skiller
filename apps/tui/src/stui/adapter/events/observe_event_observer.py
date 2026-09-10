from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import aclosing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from stui.adapter.events.cli_observe_adapter import CliObserveAdapter
from stui.adapter.events.cli_observe_frame import (
    CliObserveEventFrame,
    CliObserveFrame,
    CliObserveStartFrame,
    CliObserveStopFrame,
)
from stui.adapter.events.log_event_mapper import LogEventMapper
from stui.port.event_models import ErrorPayload, LogEvent, LogEventType
from stui.port.event_port import LogEventsListener, LogEventsObserver

MAX_UNEXPECTED_EOF_RECONNECTS = 2


class CliObserveSource(Protocol):
    def stream(
        self,
        *,
        run_id: str,
        after_sequence: int | None,
        tail: int,
    ) -> AsyncGenerator[CliObserveFrame, None]: ...


@dataclass
class ObserveEventObserver(LogEventsObserver):
    source: CliObserveSource = field(default_factory=CliObserveAdapter)
    mapper: LogEventMapper = field(default_factory=LogEventMapper)
    _listener: LogEventsListener | None = field(default=None, init=False, repr=False)
    _run_id: str = field(default="", init=False, repr=False)
    _task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)
    _generation: int = field(default=0, init=False, repr=False)

    def subscribe(
        self,
        *,
        run_id: str,
        listener: LogEventsListener,
        after_sequence: int | None,
        tail: int,
    ) -> None:
        normalized_run_id = run_id.strip()
        if not normalized_run_id:
            raise RuntimeError("observe observer requires run_id")

        if (
            self._run_id == normalized_run_id
            and self._listener is listener
            and self._task is not None
            and not self._task.done()
        ):
            return

        self._stop_current()
        self._generation += 1
        self._run_id = normalized_run_id
        self._listener = listener
        self._task = asyncio.create_task(
            self._observe(
                generation=self._generation,
                run_id=normalized_run_id,
                listener=listener,
                after_sequence=after_sequence,
                tail=tail,
            )
        )

    def unsubscribe(self) -> None:
        self._generation += 1
        self._stop_current()
        self._run_id = ""
        self._listener = None

    def _stop_current(self) -> None:
        if self._task is None or self._task.done():
            self._task = None
            return
        self._task.cancel()
        self._task = None

    async def _observe(
        self,
        *,
        generation: int,
        run_id: str,
        listener: LogEventsListener,
        after_sequence: int | None,
        tail: int,
    ) -> None:
        cursor = after_sequence
        try:
            for reconnect_count in range(MAX_UNEXPECTED_EOF_RECONNECTS + 1):
                stream = self.source.stream(
                    run_id=run_id,
                    after_sequence=cursor,
                    tail=tail,
                )
                async with aclosing(stream):
                    async for frame in stream:
                        if not self._is_current(generation, listener):
                            return
                        if isinstance(frame, CliObserveStartFrame):
                            cursor = frame.effective_after
                            continue
                        if isinstance(frame, CliObserveEventFrame):
                            event = self.mapper.map(frame.event)
                            cursor = event.sequence
                            listener.notify([event])
                            continue
                        if isinstance(frame, CliObserveStopFrame):
                            return
                if reconnect_count == MAX_UNEXPECTED_EOF_RECONNECTS:
                    raise RuntimeError("observe stream ended before stop")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if self._is_current(generation, listener):
                self._notify_error(listener=listener, run_id=run_id, cursor=cursor, exc=exc)
        finally:
            if self._is_current(generation, listener):
                self._task = None

    def _is_current(self, generation: int, listener: LogEventsListener) -> bool:
        return self._generation == generation and self._listener is listener

    def _notify_error(
        self,
        *,
        listener: LogEventsListener,
        run_id: str,
        cursor: int | None,
        exc: Exception,
    ) -> None:
        listener.notify(
            [
                LogEvent(
                    sequence=cursor or 0,
                    event_id=f"observe-error:{run_id}:{self._generation}",
                    run_id=run_id,
                    event_type=LogEventType.OBSERVER_LOOP_ERROR,
                    step_id=None,
                    step_type=None,
                    agent_sequence=None,
                    created_at=datetime.now(UTC).isoformat(),
                    payload=ErrorPayload(
                        error=f"{type(exc).__name__}: {str(exc).strip() or 'observer error'}"
                    ),
                )
            ]
        )
