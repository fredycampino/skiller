from typing import Protocol

from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import Run, RunStatus


class RunStorePort(Protocol):
    def create_run(
        self,
        skill_source: str,
        skill_ref: str,
        skill_snapshot: dict[str, object],
        context: RunContext,
        *,
        run_id: str,
    ) -> str: ...

    def update_run(
        self,
        run_id: str,
        *,
        status: RunStatus | None = None,
        current: str | None = None,
        context: RunContext | None = None,
    ) -> None: ...

    def get_run(self, run_id: str) -> Run | None: ...
