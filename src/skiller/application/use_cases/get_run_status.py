from skiller.application.ports.state_store_port import StateStorePort
from skiller.domain.run_model import Run


class GetRunStatusUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, run_id: str) -> Run | None:
        return self.store.get_run(run_id)
