from typing import Protocol

from skiller.domain.agent.agent_context_model import (
    AgentContextEntry,
    AgentContextUsageMarker,
)
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

    def append_tool_calls_assistant_message(
        self,
        *,
        context: AgentContext,
        turn_id: str,
        text: str,
        usage: LLMUsage | None,
        delta_tokens: int,
        window_start_sequence: int,
        window_base: bool,
    ) -> AgentContextEntry: ...

    def append_final_assistant_message(
        self,
        *,
        context: AgentContext,
        turn_id: str,
        text: str,
        usage: LLMUsage | None,
        delta_tokens: int,
        window_start_sequence: int,
        window_base: bool,
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

    def list_window_entries(
        self,
        *,
        context_id: str,
        window_width_tokens: int,
    ) -> list[AgentContextEntry]: ...

    def get_last_usage_marker(
        self,
        *,
        context_id: str,
    ) -> AgentContextUsageMarker | None: ...

    def next_turn_id(self, *, context_id: str) -> str: ...
