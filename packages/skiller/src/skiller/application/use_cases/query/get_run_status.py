from skiller.domain.run.run_model import Run
from skiller.domain.run.run_store_port import RunStorePort


class GetRunStatusUseCase:
    def __init__(self, store: RunStorePort) -> None:
        self.store = store

    def execute(self, run_id: str) -> Run | None:
        return self.store.get_run(run_id)
