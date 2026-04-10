from skiller.application.ports.run_store_port import RunStorePort
from skiller.domain.run_model import Run


class GetRunStatusUseCase:
    def __init__(self, store: RunStorePort) -> None:
        self.store = store

    def execute(self, run_id: str) -> Run | None:
        return self.store.get_run(run_id)
