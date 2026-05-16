from typing import Protocol

from skiller.domain.agent.agent_context_model import AgentContextEntry
from skiller.domain.agent.agent_run_scope import AgentRunScope
from skiller.domain.agent.llm_model import LLMUsage
from skiller.domain.tool.tool_execution_model import AgentToolCall, AgentToolResult


class AgentContextStorePort(Protocol):
    def init_db(self) -> None: ...

    def append_user_message(
        self,
        *,
        scope: AgentRunScope,
        text: str,
    ) -> AgentContextEntry: ...

    def append_assistant_message(
        self,
        *,
        scope: AgentRunScope,
        turn_id: str,
        message_type: str,
        text: str,
        usage: LLMUsage | None = None,
    ) -> AgentContextEntry: ...

    def append_tool_call(
        self,
        *,
        scope: AgentRunScope,
        tool_call: AgentToolCall,
    ) -> AgentContextEntry: ...

    def append_tool_result(
        self,
        *,
        scope: AgentRunScope,
        tool_result: AgentToolResult,
    ) -> AgentContextEntry: ...

    def list_entries(self, *, scope: AgentRunScope) -> list[AgentContextEntry]: ...

    def next_turn_id(self, *, scope: AgentRunScope) -> str: ...
