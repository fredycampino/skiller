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
    AgentContextObservedStats,
    AgentContextObservedWindowStats,
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
        window_tokens: int,
        window_start_sequence: int,
    ) -> AgentContextEntry:
        base_position_tokens = self.datasource.position_before_sequence(
            context_id=context.context_id,
            sequence=window_start_sequence,
        )
        position_tokens = base_position_tokens + window_tokens

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
            position_tokens=position_tokens,
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
        window_end = self.datasource.window_end_boundary(context_id=context_id)
        if window_end is None:
            entries = self.datasource.list_entries(context_id=context_id)
            return AgentContextWindow(
                entries=entries,
                start_sequence=_start_sequence(entries),
                end_sequence=_end_sequence(entries),
            )

        window_start_position_tokens = window_end.position_tokens - window_tokens
        if window_start_position_tokens <= 0:
            entries = self.datasource.list_entries(context_id=context_id)
            return AgentContextWindow(
                entries=entries,
                start_sequence=_start_sequence(entries),
                end_sequence=_end_sequence(entries),
            )

        base_position_tokens = self.datasource.position_before_sequence(
            context_id=context_id,
            sequence=window_end.window_start_sequence,
        )
        if window_start_position_tokens > base_position_tokens:
            window_start = self.datasource.window_start_boundary_for_start_sequence(
                context_id=context_id,
                window_start_sequence=window_end.window_start_sequence,
                window_start_position_tokens=window_start_position_tokens,
            )
            sequence = window_end.window_start_sequence
            if window_start is not None:
                sequence = window_start.sequence
            entries = self.datasource.list_entries_from_sequence(
                context_id=context_id,
                sequence=sequence,
            )
            return AgentContextWindow(
                entries=entries,
                start_sequence=_start_sequence(entries),
                end_sequence=_end_sequence(entries),
            )

        window_start = self.datasource.window_start_boundary(
            context_id=context_id,
            window_start_position_tokens=window_start_position_tokens,
        )
        if window_start is None:
            entries = self.datasource.list_entries(context_id=context_id)
            return AgentContextWindow(
                entries=entries,
                start_sequence=_start_sequence(entries),
                end_sequence=_end_sequence(entries),
            )

        entries = self.datasource.list_entries_from_sequence(
            context_id=context_id,
            sequence=window_start.sequence,
        )
        return AgentContextWindow(
            entries=entries,
            start_sequence=_start_sequence(entries),
            end_sequence=_end_sequence(entries),
        )

    def get_stats(self, *, context_id: str) -> AgentContextObservedStats:
        entries = self.datasource.list_entries(context_id=context_id)
        final_entry = _last_final_entry(entries)
        if final_entry is None:
            start_sequence = _start_sequence(entries)
            return AgentContextObservedStats(
                entries=len(entries),
                estimated_tokens=0,
                window=AgentContextObservedWindowStats(
                    start_sequence=start_sequence,
                    end_sequence=_end_sequence(entries),
                    current_tokens=0,
                ),
            )

        window_start_sequence = final_entry.window_start_sequence or 0

        return AgentContextObservedStats(
            entries=len(entries),
            estimated_tokens=final_entry.position_tokens or 0,
            window=AgentContextObservedWindowStats(
                start_sequence=window_start_sequence,
                end_sequence=_end_sequence(entries),
                current_tokens=final_entry.window_tokens or 0,
            ),
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
