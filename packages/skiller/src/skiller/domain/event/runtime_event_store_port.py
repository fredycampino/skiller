from typing import Protocol

from skiller.domain.event.event_model import RuntimeEvent, RuntimeEventDraft


class RuntimeEventStorePort(Protocol):
    def append_event(self, event: RuntimeEventDraft) -> str: ...

    def list_events(
        self,
        run_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[RuntimeEvent]: ...

    def get_last_event(self, run_id: str) -> RuntimeEvent | None: ...
