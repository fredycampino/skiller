from skiller.domain.run.run_status_runtime_model import RunStatusRuntime
from skiller.domain.run.run_store_port import RunStorePort


class GetRunStatusUseCase:
    def __init__(self, store: RunStorePort) -> None:
        self.store = store

    def execute(self, run_id: str) -> RunStatusRuntime | None:
        return self.store.get_status(run_id)
