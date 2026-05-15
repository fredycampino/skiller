from typing import Protocol

from skiller.domain.agent.agent_context_model import AgentContextEntry
from skiller.domain.event.event_model import RuntimeEvent, RuntimeEventDraft


class RuntimeEventStorePort(Protocol):
    def emit_max_turns_exhausted(
        self,
        *,
        run_id: str,
        step_id: str,
        turn_id: str,
    ) -> None: ...

    def emit_interrupted(
        self,
        *,
        run_id: str,
        step_id: str,
        turn_id: str,
    ) -> None: ...

    def emit_assistant_message(
        self,
        *,
        entry: AgentContextEntry,
    ) -> None: ...

    def emit_tool_call(
        self,
        *,
        entry: AgentContextEntry,
    ) -> None: ...

    def emit_tool_result(
        self,
        *,
        entry: AgentContextEntry,
    ) -> None: ...

    def append_event(self, event: RuntimeEventDraft) -> str: ...

    def list_events(
        self,
        run_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[RuntimeEvent]: ...

    def get_last_event(self, run_id: str) -> RuntimeEvent | None: ...
