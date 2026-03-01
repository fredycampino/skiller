from typing import Any

from runtime.application.ports.state_store import StateStorePort


class GetRunStatusUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, run_id: str) -> dict[str, Any] | None:
        return self.store.get_run(run_id)
