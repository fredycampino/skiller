from typing import Protocol

from skiller.domain.agent.agent_context_model import (
    AgentContextEntry,
    AgentContextToolCall,
    AgentContextToolResult,
)
from skiller.domain.agent.agent_run_scope import AgentRunScope


class AgentContextStorePort(Protocol):
    def init_db(self) -> None: ...

    def append_user_message(
        self,
        *,
        scope: AgentRunScope,
        turn_id: str,
        text: str,
    ) -> AgentContextEntry: ...

    def append_assistant_message(
        self,
        *,
        scope: AgentRunScope,
        turn_id: str,
        message_type: str,
        text: str,
    ) -> AgentContextEntry: ...

    def append_tool_call(
        self,
        *,
        scope: AgentRunScope,
        turn_id: str,
        parent_sequence: int | None,
        tool_call: AgentContextToolCall,
    ) -> AgentContextEntry: ...

    def append_tool_result(
        self,
        *,
        scope: AgentRunScope,
        turn_id: str,
        parent_sequence: int | None,
        tool_result: AgentContextToolResult,
    ) -> AgentContextEntry: ...

    def list_entries(self, *, scope: AgentRunScope) -> list[AgentContextEntry]: ...

    def next_turn_id(self, *, scope: AgentRunScope) -> str: ...
