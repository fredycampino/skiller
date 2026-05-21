from typing import Protocol

from skiller.domain.agent.agent_context_model import AgentContextEntry
from skiller.domain.agent.agent_run_identity import AgentContext
from skiller.domain.agent.llm_model import LLMUsage
from skiller.domain.tool.tool_execution_model import AgentToolCall, AgentToolResult


class AgentContextStorePort(Protocol):
    def append_user_message(
        self,
        *,
        context: AgentContext,
        text: str,
    ) -> AgentContextEntry: ...

    def append_assistant_message(
        self,
        *,
        context: AgentContext,
        turn_id: str,
        message_type: str,
        text: str,
        usage: LLMUsage | None = None,
    ) -> AgentContextEntry: ...

    def append_tool_call(
        self,
        *,
        context: AgentContext,
        tool_call: AgentToolCall,
    ) -> AgentContextEntry: ...

    def append_tool_result(
        self,
        *,
        context: AgentContext,
        tool_result: AgentToolResult,
    ) -> AgentContextEntry: ...

    def list_entries(self, *, context_id: str) -> list[AgentContextEntry]: ...

    def list_context_window(
        self,
        *,
        context_id: str,
        window_tokens: int,
    ) -> list[AgentContextEntry]: ...

    def next_turn_id(self, *, context_id: str) -> str: ...
