from skiller.application.ports.run_store_port import RunStorePort
from skiller.domain.run_model import RunStatus


class CompleteRunUseCase:
    def __init__(self, store: RunStorePort) -> None:
        self.store = store

    def execute(self, run_id: str) -> None:
        self.store.update_run(
            run_id,
            status=RunStatus.SUCCEEDED,
        )
