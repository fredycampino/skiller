from skiller.domain.event.event_model import RuntimeEvent
from skiller.domain.event.runtime_event_store_port import RuntimeEventStorePort


class GetRunLogsUseCase:
    def __init__(self, store: RuntimeEventStorePort) -> None:
        self.store = store

    def execute(
        self,
        run_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[RuntimeEvent]:
        return self.store.list_events(
            run_id,
            after_sequence=after_sequence,
            limit=limit,
        )

    def latest(self, run_id: str) -> RuntimeEvent | None:
        return self.store.get_last_event(run_id)
