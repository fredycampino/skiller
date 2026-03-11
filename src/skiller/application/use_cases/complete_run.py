from skiller.application.ports.state_store_port import StateStorePort
from skiller.domain.run_model import RunStatus


class CompleteRunUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, run_id: str) -> None:
        self.store.update_run(
            run_id,
            status=RunStatus.SUCCEEDED,
        )
        self.store.append_event(
            "RUN_FINISHED",
            {"status": RunStatus.SUCCEEDED.value},
            run_id=run_id,
        )
