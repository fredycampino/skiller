from typing import Protocol


class AgentRunScope(Protocol):
    @property
    def run_id(self) -> str: ...

    @property
    def agent_id(self) -> str: ...

    @property
    def context_id(self) -> str: ...
