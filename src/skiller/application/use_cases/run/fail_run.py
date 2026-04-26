from skiller.application.ports.run_store_port import RunStorePort
from skiller.domain.run.run_model import RunStatus


class FailRunUseCase:
    def __init__(self, store: RunStorePort) -> None:
        self.store = store

    def execute(self, run_id: str, *, error: str) -> None:
        run = self.store.get_run(run_id)
        self.store.update_run(
            run_id,
            status=RunStatus.FAILED,
            current=(run.current if run else None),
            context=(run.context if run else None),
        )
