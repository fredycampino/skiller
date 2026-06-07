from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessagePayload,
    AgentAssistantMessageType,
    AgentContextEntry,
    AgentContextEntryType,
    AgentContextUsageMarker,
    AgentToolCallPayload,
    AgentToolResultPayload,
    AgentUserMessagePayload,
)
from skiller.domain.agent.agent_context_stats_port import AgentContextStatsPort
from skiller.domain.agent.agent_context_store_port import AgentContextStorePort
from skiller.domain.agent.agent_run_identity import AgentContext
from skiller.domain.agent.agent_stats_model import (
    AgentContextObservedStats,
)
from skiller.domain.agent.llm_model import LLMUsage
from skiller.domain.tool.tool_execution_model import AgentToolCall, AgentToolResult
from skiller.infrastructure.db.datasource.sqlite_agent_context_datasource import (
    SqliteAgentContextDatasource,
)


class AgentContextStore(
    AgentContextStorePort,
    AgentContextStatsPort,
):
    def __init__(self, datasource: SqliteAgentContextDatasource) -> None:
        self.datasource = datasource

    def append_user_message(
        self,
        *,
        context: AgentContext,
        text: str,
    ) -> AgentContextEntry:
        return self.datasource.append_entry(
            run_id=context.run_id,
            context_id=context.context_id,
            entry_type=AgentContextEntryType.USER_MESSAGE,
            payload=AgentUserMessagePayload(text=text),
            source_step_id=context.agent_id,
        )

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
    ) -> AgentContextEntry:
        return self.datasource.append_entry(
            run_id=context.run_id,
            context_id=context.context_id,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            payload=AgentAssistantMessagePayload(
                turn_id=turn_id,
                message_type=AgentAssistantMessageType.TOOL_CALLS,
                text=text,
            ),
            usage=usage,
            window_start_sequence=window_start_sequence,
            delta_tokens=delta_tokens,
            window_base=window_base,
            source_step_id=context.agent_id,
        )

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
    ) -> AgentContextEntry:
        return self.datasource.append_entry(
            run_id=context.run_id,
            context_id=context.context_id,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            payload=AgentAssistantMessagePayload(
                turn_id=turn_id,
                message_type=AgentAssistantMessageType.FINAL,
                text=text,
            ),
            usage=usage,
            window_start_sequence=window_start_sequence,
            delta_tokens=delta_tokens,
            window_base=window_base,
            source_step_id=context.agent_id,
        )

    def append_tool_call(
        self,
        *,
        context: AgentContext,
        tool_call: AgentToolCall,
    ) -> AgentContextEntry:
        return self.datasource.append_entry(
            run_id=context.run_id,
            context_id=context.context_id,
            entry_type=AgentContextEntryType.TOOL_CALL,
            payload=AgentToolCallPayload(
                turn_id=tool_call.turn_id,
                parent_sequence=tool_call.parent_sequence,
                tool_call_id=tool_call.tool_call_id,
                tool=tool_call.tool,
                args=tool_call.args,
            ),
            source_step_id=context.agent_id,
        )

    def append_tool_result(
        self,
        *,
        context: AgentContext,
        tool_result: AgentToolResult,
    ) -> AgentContextEntry:
        result = tool_result.result
        return self.datasource.append_entry(
            run_id=context.run_id,
            context_id=context.context_id,
            entry_type=AgentContextEntryType.TOOL_RESULT,
            payload=AgentToolResultPayload(
                turn_id=tool_result.turn_id,
                parent_sequence=tool_result.parent_sequence,
                tool_call_id=tool_result.tool_call_id,
                tool=result.name,
                status=result.status.value,
                data=result.data,
                error=result.error,
            ),
            source_step_id=context.agent_id,
        )

    def list_entries(self, *, context_id: str) -> list[AgentContextEntry]:
        return self.datasource.list_entries(context_id=context_id)

    def list_window_entries(
        self,
        *,
        context_id: str,
        window_width_tokens: int,
    ) -> list[AgentContextEntry]:
        return self.datasource.list_window_entries(
            context_id=context_id,
            window_width_tokens=window_width_tokens,
        )

    def get_last_usage_marker(
        self,
        *,
        context_id: str,
    ) -> AgentContextUsageMarker | None:
        return self.datasource.get_last_usage_marker(context_id=context_id)

    def get_stats(self, *, context_id: str) -> AgentContextObservedStats:
        return self.datasource.get_observed_stats(context_id=context_id)

    def get_usage(self, *, context_id: str) -> LLMUsage:
        entries = self.datasource.list_entries(context_id=context_id)
        usage = _last_final_usage_from_entries(entries)
        return usage or _empty_usage()

    def next_turn_id(self, *, context_id: str) -> str:
        return self.datasource.next_turn_id(context_id=context_id)


def _empty_usage() -> LLMUsage:
    return LLMUsage(
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )


def _last_final_usage_from_entries(entries: list[AgentContextEntry]) -> LLMUsage | None:
    entry = _last_final_entry(entries)
    if entry is None:
        return None
    return entry.usage


def _last_final_entry(entries: list[AgentContextEntry]) -> AgentContextEntry | None:
    for entry in reversed(entries):
        if entry.entry_type != AgentContextEntryType.ASSISTANT_MESSAGE:
            continue
        if not isinstance(entry.payload, AgentAssistantMessagePayload):
            continue
        if entry.payload.message_type != AgentAssistantMessageType.FINAL:
            continue
        return entry
    return None
