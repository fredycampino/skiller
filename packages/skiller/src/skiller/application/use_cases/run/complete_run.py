from skiller.domain.run.run_model import RunStatus
from skiller.domain.run.run_store_port import RunStorePort


class CompleteRunUseCase:
    def __init__(self, store: RunStorePort) -> None:
        self.store = store

    def execute(self, run_id: str) -> None:
        self.store.update_run(
            run_id,
            status=RunStatus.SUCCEEDED,
        )
