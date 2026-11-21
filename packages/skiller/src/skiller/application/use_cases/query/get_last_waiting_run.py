from pathlib import Path

from skiller.domain.run.run_model import Run
from skiller.domain.run.run_query_port import RunQueryPort


class GetLastWaitingRunUseCase:
    def __init__(self, store: RunQueryPort) -> None:
        self.store = store

    def execute(self, flow_path: Path) -> Run | None:
        return self.store.get_last_waiting_run(flow_path)
