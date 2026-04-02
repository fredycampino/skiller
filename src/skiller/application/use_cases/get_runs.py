from skiller.application.ports.run_query_port import RunQueryPort
from skiller.domain.run_list_item_model import RunListItem


class GetRunsUseCase:
    def __init__(self, store: RunQueryPort) -> None:
        self.store = store

    def execute(self, *, limit: int = 20, statuses: list[str] | None = None) -> list[RunListItem]:
        return self.store.list_runs(limit=limit, statuses=statuses)
