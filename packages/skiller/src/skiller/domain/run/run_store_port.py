from typing import Protocol

from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run, RunAgent, RunStatus


class RunStorePort(Protocol):
    def create_run(
        self,
        source: str,
        ref: str,
        snapshot: dict[str, object],
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

    def get_agent(
        self,
        *,
        run_id: str,
        agent_id: str,
    ) -> RunAgent | None: ...

    def attach_agent(
        self,
        *,
        run_id: str,
        agent_id: str,
        context_id: str,
    ) -> None: ...

    def delete_run(self, run_id: str) -> bool: ...
