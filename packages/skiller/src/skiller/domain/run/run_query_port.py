from pathlib import Path
from typing import Protocol

from skiller.domain.run.run_list_item_model import RunListItem
from skiller.domain.run.run_model import Run


class RunQueryPort(Protocol):
    def get_last_waiting_run(self, flow_path: Path) -> Run | None: ...

    def list_runs(
        self,
        *,
        limit: int = 20,
        statuses: list[str] | None = None,
    ) -> list[RunListItem]: ...
