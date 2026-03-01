from typing import Any

from runtime.application.ports.state_store import StateStorePort


class GetRunLogsUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, run_id: str) -> list[dict[str, Any]]:
        return self.store.list_events(run_id)
