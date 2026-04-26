from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any

from skiller.domain.run.run_model import RunStatus
from skiller.interfaces.tui.adapter.run_event_mapper import RunEventMapper
from skiller.interfaces.tui.port.run_port import (
    ObserverType,
    PollingEvent,
    PollingEventKind,
    RunObserver,
)

_TERMINAL_STATUSES = {
    RunStatus.WAITING.value,
    RunStatus.SUCCEEDED.value,
    RunStatus.FAILED.value,
    RunStatus.CANCELLED.value,
}


@dataclass
class PollingEventObserver:
    interval_seconds: float = 0.1
    mapper: RunEventMapper = field(default_factory=RunEventMapper)
    _observer: RunObserver | None = field(default=None, init=False, repr=False)
    _task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)
    _last_status: str = field(default="", init=False, repr=False)
    _seen_event_ids: set[str] = field(default_factory=set, init=False, repr=False)

    def subscribe(self, observer: RunObserver) -> None:
        if observer.type != ObserverType.RUN:
            raise RuntimeError(f"Unsupported observer type: {observer.type}")

        if self._contains_run_observer(observer):
            return

        self.unsubscribe_current()
        self._observer = observer
        self._last_status = ""
        self._seen_event_ids = set()
        self._task = asyncio.create_task(self._poll_loop(observer))

    def unsubscribe(self, observer: RunObserver) -> None:
        if not self._contains_run_observer(observer):
            return

        self.unsubscribe_current()

    def unsubscribe_current(self) -> None:
        self._observer = None
        self._last_status = ""
        self._seen_event_ids = set()
        if self._task is None or self._task.done():
            self._task = None
            return

        self._task.cancel()
        self._task = None

    async def _poll_loop(self, observer: RunObserver) -> None:
        try:
            while self._observer is observer:
                events = await self._poll_run_events(observer)
                if events:
                    observer.notify(events)
                if self._consume_status_events(events):
                    self._observer = None
                    return

                if self._observer is not observer:
                    return

                await asyncio.sleep(self.interval_seconds)
        except asyncio.CancelledError:
            raise
        finally:
            self._task = None

    async def _poll_run_events(
        self,
        observer: RunObserver,
    ) -> list[PollingEvent]:
        run_id = observer.run_id
        status_payload = await asyncio.to_thread(_run_json_command, "status", run_id)
        events_payload = await asyncio.to_thread(_run_json_list_command, "logs", run_id)

        observed = self.mapper.logs_to_events(
            run_id=run_id,
            events_payload=events_payload,
            seen_event_ids=self._seen_event_ids,
        )
        status_event = self.mapper.status_to_event(
            run_id=run_id,
            status_payload=status_payload,
            last_status=self._last_status,
        )
        if status_event is not None:
            observed.append(status_event)
        return observed

    def _contains_run_observer(self, observer: RunObserver) -> bool:
        if self._observer is None:
            return False
        return _is_same_run_observer(self._observer, observer)

    def _consume_status_events(self, events: list[PollingEvent]) -> bool:
        is_terminal = False
        for event in events:
            if event.kind != PollingEventKind.STATUS:
                continue
            self._last_status = event.status
            if event.status in _TERMINAL_STATUSES:
                is_terminal = True
        return is_terminal


def _is_same_run_observer(left: RunObserver, right: RunObserver) -> bool:
    return left.run_id == right.run_id


def _run_json_command(*args: str) -> dict[str, Any]:
    completed = _run_cli_command(*args)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "runtime command failed"
        raise RuntimeError(detail)

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("runtime command returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("runtime command returned invalid payload")
    return payload


def _run_json_list_command(*args: str) -> list[dict[str, Any]]:
    completed = _run_cli_command(*args)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "runtime command failed"
        raise RuntimeError(detail)

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("runtime command returned invalid JSON") from exc

    if not isinstance(payload, list):
        raise RuntimeError("runtime command returned invalid payload")
    return [item for item in payload if isinstance(item, dict)]


def _run_cli_command(*args: str) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "skiller", *args]
    return subprocess.run(  # noqa: S603
        command,
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
    )
