from typing import Protocol


class RuntimeEventStorePort(Protocol):
    def append_event(
        self, event_type: str, payload: dict[str, object], run_id: str | None = None
    ) -> str: ...

    def list_events(self, run_id: str) -> list[dict[str, object]]: ...
