from typing import Protocol

from runtime.domain.models import Event


class EventBusPort(Protocol):
    def publish(self, event: Event) -> None:
        ...

    def consume(self) -> Event | None:
        ...
