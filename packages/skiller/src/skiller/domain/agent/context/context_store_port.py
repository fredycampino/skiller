from typing import Protocol

from skiller.domain.agent.context.model import (
    AgentContextCompactionQuery,
    AgentContextEntry,
    AgentContextPayload,
    AgentContextState,
    AgentContextUsageMarker,
    AgentContextWindowEntries,
    AgentContextWindowQuery,
)
from skiller.domain.agent.llm.model import LLMUsage
from skiller.domain.agent.run.identity import AgentContext
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
        compaction_id: int | None,
    ) -> AgentContextEntry: ...

    def append_final_assistant_message(
        self,
        *,
        context: AgentContext,
        turn_id: str,
        text: str,
        usage: LLMUsage | None,
        delta_tokens: int,
        compaction_id: int | None,
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

    def list_entries_from_sequence(
        self,
        *,
        context_id: str,
        start_sequence: int,
    ) -> list[AgentContextEntry]: ...

    def list_raw_entries(
        self,
        *,
        query: AgentContextWindowQuery,
    ) -> AgentContextWindowEntries: ...

    def list_compact_entries(
        self,
        *,
        query: AgentContextWindowQuery,
    ) -> AgentContextWindowEntries: ...

    def select_compaction_state(
        self,
        *,
        query: AgentContextCompactionQuery,
    ) -> AgentContextState: ...

    def get_last_usage_marker(
        self,
        *,
        context_id: str,
    ) -> AgentContextUsageMarker | None: ...

    def estimate_window_tokens(
        self,
        *,
        context_id: str,
        start_sequence: int,
    ) -> int: ...

    def estimate_delta_tokens(
        self,
        *,
        context_id: str,
        start_sequence: int,
        last_marker_sequence: int,
        payload: AgentContextPayload,
    ) -> int: ...

    def add_compact_delta_tokens(
        self,
        *,
        context_id: str,
        marker_sequence: int,
    ) -> None: ...

    def next_turn_id(self, *, context_id: str) -> str: ...
