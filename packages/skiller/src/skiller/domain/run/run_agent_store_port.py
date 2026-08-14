from typing import Protocol

from skiller.domain.run.run_model import RunAgent


class RunAgentStorePort(Protocol):
    def get_agent(
        self,
        *,
        run_id: str,
        agent_id: str,
    ) -> RunAgent | None: ...

    def get_first_agent(self, *, run_id: str) -> RunAgent | None: ...

    def attach_agent(
        self,
        *,
        run_id: str,
        agent_id: str,
        context_id: str,
    ) -> None: ...
