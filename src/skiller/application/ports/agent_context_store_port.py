from typing import Protocol

from skiller.domain.agent.agent_context_model import AgentContextEntry, AgentContextEntryType


class AgentContextStorePort(Protocol):
    def init_db(self) -> None: ...

    def append_entry(
        self,
        *,
        run_id: str,
        context_id: str,
        entry_type: AgentContextEntryType,
        payload: dict[str, object],
        source_step_id: str,
        idempotency_key: str,
    ) -> AgentContextEntry: ...

    def list_entries(self, *, run_id: str, context_id: str) -> list[AgentContextEntry]: ...
