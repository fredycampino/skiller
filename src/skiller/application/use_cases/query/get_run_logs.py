from typing import Any

from skiller.application.ports.runtime_event_store_port import RuntimeEventStorePort


class GetRunLogsUseCase:
    def __init__(self, store: RuntimeEventStorePort) -> None:
        self.store = store

    def execute(self, run_id: str) -> list[dict[str, Any]]:
        return self.store.list_events(run_id)
