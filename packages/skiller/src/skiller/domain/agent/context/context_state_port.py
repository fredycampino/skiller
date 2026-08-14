from typing import Protocol

from skiller.domain.agent.context.model import AgentContextState


class AgentContextStatePort(Protocol):
    def get_state(self, *, context_id: str) -> AgentContextState: ...

    def save_state(self, *, state: AgentContextState) -> None: ...
