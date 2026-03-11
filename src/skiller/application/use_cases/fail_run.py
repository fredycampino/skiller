from skiller.application.ports.state_store_port import StateStorePort
from skiller.domain.run_model import RunStatus


class FailRunUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, run_id: str, *, error: str) -> None:
        run = self.store.get_run(run_id)
        self.store.update_run(
            run_id,
            status=RunStatus.FAILED,
            current=(run.current if run else None),
            context=(run.context if run else None),
        )
        self.store.append_event("RUN_FAILED", {"error": error}, run_id=run_id)
