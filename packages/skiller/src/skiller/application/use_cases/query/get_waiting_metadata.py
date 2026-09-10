from skiller.application.waits.waiting_metadata_resolver import (
    WaitingMetadata,
    WaitingMetadataResolver,
)
from skiller.domain.run.run_model import Run
from skiller.domain.run.run_store_port import RunStorePort


class GetWaitingMetadataUseCase:
    def __init__(self, store: RunStorePort, resolver: WaitingMetadataResolver) -> None:
        self.store = store
        self.resolver = resolver

    def execute(self, run_id: str) -> WaitingMetadata | None:
        run = self.store.get_run(run_id)
        if run is None:
            return None
        return self.execute_for_run(run)

    def execute_for_run(self, run: Run) -> WaitingMetadata | None:
        return self.resolver.resolve(run)
