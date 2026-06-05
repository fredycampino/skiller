from typing import Protocol

from skiller.domain.run.run_model import RunAgent, RunAgentWindow


class RunAgentStorePort(Protocol):
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

    def update_agent_window(
        self,
        *,
        run_id: str,
        window: RunAgentWindow,
    ) -> None: ...
