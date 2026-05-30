from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessagePayload,
    AgentAssistantMessageType,
    AgentContextEntry,
    AgentContextEntryType,
    AgentContextWindow,
    AgentToolCallPayload,
    AgentToolResultPayload,
    AgentUserMessagePayload,
)
from skiller.domain.agent.agent_context_stats_port import AgentContextStatsPort
from skiller.domain.agent.agent_context_store_port import AgentContextStorePort
from skiller.domain.agent.agent_run_identity import AgentContext
from skiller.domain.agent.agent_stats_model import (
    AgentContextEntryStats,
    AgentContextStats,
    AgentContextUsageStats,
)
from skiller.domain.agent.llm_model import LLMUsage
from skiller.domain.tool.tool_execution_model import AgentToolCall, AgentToolResult
from skiller.infrastructure.db.sqlite_agent_context_datasource import (
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
            source_step_id=context.agent_id,
        )

    def append_final_assistant_message(
        self,
        *,
        context: AgentContext,
        turn_id: str,
        text: str,
        usage: LLMUsage | None,
        window_tokens: int | None,
        window_start_sequence: int,
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
            window_tokens=window_tokens,
            window_start_sequence=window_start_sequence,
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
                text=result.text,
                error=result.error,
            ),
            source_step_id=context.agent_id,
        )

    def list_entries(self, *, context_id: str) -> list[AgentContextEntry]:
        return self.datasource.list_entries(context_id=context_id)

    def list_context_window(
        self,
        *,
        context_id: str,
        window_tokens: int,
    ) -> AgentContextWindow:
        current_marker = self.datasource.current_marker(context_id=context_id)
        if current_marker is None:
            entries = self.datasource.list_entries(context_id=context_id)
            return AgentContextWindow(
                entries=entries,
                start_sequence=_start_sequence(entries),
                end_sequence=_end_sequence(entries),
            )

        if current_marker.window_tokens <= window_tokens:
            entries = self.datasource.list_entries_from_sequence(
                context_id=context_id,
                sequence=current_marker.window_start_sequence,
            )
            return AgentContextWindow(
                entries=entries,
                start_sequence=_start_sequence(entries),
                end_sequence=_end_sequence(entries),
            )

        cutoff_tokens = current_marker.window_tokens - window_tokens
        cutoff_marker = self.datasource.cutoff_marker(
            context_id=context_id,
            start_sequence=current_marker.window_start_sequence,
            cutoff_tokens=cutoff_tokens,
        )
        if cutoff_marker is None:
            entries = self.datasource.list_entries_from_sequence(
                context_id=context_id,
                sequence=current_marker.window_start_sequence,
            )
            return AgentContextWindow(
                entries=entries,
                start_sequence=_start_sequence(entries),
                end_sequence=_end_sequence(entries),
            )

        entries = self.datasource.list_entries_from_sequence(
            context_id=context_id,
            sequence=max(current_marker.window_start_sequence, cutoff_marker.sequence),
        )
        return AgentContextWindow(
            entries=entries,
            start_sequence=_start_sequence(entries),
            end_sequence=_end_sequence(entries),
        )

    def get_stats(self, *, context_id: str) -> AgentContextStats:
        entries = self.datasource.list_entries(context_id=context_id)
        return AgentContextStats(
            entries=_calculate_entry_stats(entries),
            usage=_calculate_usage_stats(entries),
        )

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


def _start_sequence(entries: list[AgentContextEntry]) -> int:
    if not entries:
        return 0
    return entries[0].sequence


def _end_sequence(entries: list[AgentContextEntry]) -> int:
    if not entries:
        return 0
    return entries[-1].sequence


def _calculate_entry_stats(entries: list[AgentContextEntry]) -> AgentContextEntryStats:
    user_messages = 0
    assistant_messages = 0
    tool_calls = 0
    tool_results = 0

    for entry in entries:
        if entry.entry_type == AgentContextEntryType.USER_MESSAGE:
            user_messages += 1
            continue
        if entry.entry_type == AgentContextEntryType.ASSISTANT_MESSAGE:
            assistant_messages += 1
            continue
        if entry.entry_type == AgentContextEntryType.TOOL_CALL:
            tool_calls += 1
            continue
        if entry.entry_type == AgentContextEntryType.TOOL_RESULT:
            tool_results += 1

    return AgentContextEntryStats(
        total=len(entries),
        user_messages=user_messages,
        assistant_messages=assistant_messages,
        tool_calls=tool_calls,
        tool_results=tool_results,
    )


def _calculate_usage_stats(entries: list[AgentContextEntry]) -> AgentContextUsageStats:
    usage = _last_final_usage_from_entries(entries)
    if usage is None:
        return AgentContextUsageStats(
            entries=0,
            total_prompt_tokens=0,
            total_response_tokens=0,
            total_tokens=0,
        )

    return AgentContextUsageStats(
        entries=1,
        total_prompt_tokens=usage.prompt_tokens or 0,
        total_response_tokens=usage.completion_tokens or 0,
        total_tokens=usage.total_tokens or 0,
    )


def _last_final_usage_from_entries(entries: list[AgentContextEntry]) -> LLMUsage | None:
    for entry in reversed(entries):
        if entry.entry_type != AgentContextEntryType.ASSISTANT_MESSAGE:
            continue
        if not isinstance(entry.payload, AgentAssistantMessagePayload):
            continue
        if entry.payload.message_type != AgentAssistantMessageType.FINAL:
            continue
        return entry.usage
    return None
