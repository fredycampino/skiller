from typing import Protocol

from skiller.domain.agent.agent_context_model import AgentContextEntry


class AgentContextStorePort(Protocol):
    def init_db(self) -> None: ...

    def append_user_message(
        self,
        *,
        run_id: str,
        context_id: str,
        source_step_id: str,
        turn_id: str,
        text: str,
    ) -> AgentContextEntry: ...

    def append_assistant_message(
        self,
        *,
        run_id: str,
        context_id: str,
        source_step_id: str,
        turn_id: str,
        message_type: str,
        text: str,
    ) -> AgentContextEntry: ...

    def append_tool_call(
        self,
        *,
        run_id: str,
        context_id: str,
        source_step_id: str,
        turn_id: str,
        parent_sequence: int | None,
        tool_call_id: str,
        tool: str,
        args: dict[str, object],
    ) -> AgentContextEntry: ...

    def append_tool_result(
        self,
        *,
        run_id: str,
        context_id: str,
        source_step_id: str,
        turn_id: str,
        parent_sequence: int | None,
        tool_call_id: str,
        tool: str,
        status: str,
        data: object,
        text: str | None,
        error: str | None,
    ) -> AgentContextEntry: ...

    def list_entries(self, *, run_id: str, context_id: str) -> list[AgentContextEntry]: ...
