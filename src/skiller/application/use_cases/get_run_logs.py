from typing import Any

from skiller.application.ports.state_store_port import StateStorePort


class GetRunLogsUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, run_id: str) -> list[dict[str, Any]]:
        return self.store.list_events(run_id)
