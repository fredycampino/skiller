from __future__ import annotations

import signal
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from types import FrameType
from typing import Any, Protocol

from skiller.interfaces.cli.observe_output import JsonlFrameWriter

DEFAULT_OBSERVE_POLL_INTERVAL_SECONDS = 0.5


class ObserveCancellationState(Protocol):
    @property
    def requested(self) -> bool: ...

    def wait(self, timeout_seconds: float) -> bool: ...


@dataclass
class ObserveCancellation:
    _event: threading.Event = field(default_factory=threading.Event, init=False)
    _previous_handlers: dict[signal.Signals, Any] = field(default_factory=dict, init=False)

    @property
    def requested(self) -> bool:
        return self._event.is_set()

    def install(self) -> None:
        for signal_number in (signal.SIGINT, signal.SIGTERM):
            self._previous_handlers[signal_number] = signal.getsignal(signal_number)
            signal.signal(signal_number, self._handle_signal)

    def restore(self) -> None:
        for signal_number, previous_handler in self._previous_handlers.items():
            signal.signal(signal_number, previous_handler)
        self._previous_handlers.clear()

    def request_stop(self) -> None:
        self._event.set()

    def wait(self, timeout_seconds: float) -> bool:
        return self._event.wait(timeout_seconds)

    def _handle_signal(self, _signum: int, _frame: FrameType | None) -> None:
        self.request_stop()


class ObserveCommand:
    def __init__(
        self,
        *,
        writer: JsonlFrameWriter,
        cancellation: ObserveCancellationState,
        poll_interval_seconds: float = DEFAULT_OBSERVE_POLL_INTERVAL_SECONDS,
    ) -> None:
        self.writer = writer
        self.cancellation = cancellation
        self.poll_interval_seconds = poll_interval_seconds

    def execute(self, stream: Iterator[dict[str, Any] | None]) -> int:
        iterator = iter(stream)
        while not self.cancellation.requested:
            try:
                frame = next(iterator)
            except StopIteration:
                return 0
            if frame is None:
                self.cancellation.wait(self.poll_interval_seconds)
                continue
            self.writer.write(frame)
        return 0
