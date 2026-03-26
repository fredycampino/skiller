from skiller.application.ports.state_store_port import StateStorePort
from skiller.domain.run_model import Run


class GetRunsUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, *, limit: int = 20, statuses: list[str] | None = None) -> list[Run]:
        return self.store.list_runs(limit=limit, statuses=statuses)
