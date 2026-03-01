from collections import deque

from runtime.domain.models import Event


class EventBus:
    """Minimal in-memory event bus for the POC runtime."""

    def __init__(self) -> None:
        self._queue: deque[Event] = deque()

    def publish(self, event: Event) -> None:
        self._queue.append(event)

    def consume(self) -> Event | None:
        if not self._queue:
            return None
        return self._queue.popleft()
