from typing import Protocol

from skiller.domain.run_list_item_model import RunListItem


class RunQueryPort(Protocol):
    def list_runs(
        self,
        *,
        limit: int = 20,
        statuses: list[str] | None = None,
    ) -> list[RunListItem]: ...
