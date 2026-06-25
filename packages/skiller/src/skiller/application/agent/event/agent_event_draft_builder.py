from skiller.domain.agent.context.model import (
    AgentAssistantMessagePayload,
    AgentAssistantMessageType,
    AgentContextEntry,
    AgentContextEntryType,
    AgentToolCallPayload,
    AgentToolResultPayload,
)
from skiller.domain.event.event_agent_model import (
    AgentEventPayload,
    AgentLifecyclePayload,
    AgentMessageEventBody,
    AgentToolCallEventBody,
    AgentToolResultEventBody,
)
from skiller.domain.event.event_model import RuntimeEventDraft, RuntimeEventType


class AgentEventDraftBuilder:
    def assistant_message(
        self,
        *,
        entry: AgentContextEntry,
    ) -> RuntimeEventDraft:
        if entry.entry_type != AgentContextEntryType.ASSISTANT_MESSAGE:
            raise ValueError("Assistant event requires assistant_message entry")
        if not isinstance(entry.payload, AgentAssistantMessagePayload):
            raise ValueError("Assistant event requires AgentAssistantMessagePayload")
        if entry.payload.message_type != AgentAssistantMessageType.TOOL_CALLS:
            raise ValueError("Assistant event requires tool_calls message")

        return RuntimeEventDraft(
            run_id=entry.run_id,
            type=RuntimeEventType.AGENT_ASSISTANT_MESSAGE,
            payload=AgentEventPayload(
                step_id=entry.source_step_id,
                turn_id=entry.payload.turn_id,
                agent_sequence=entry.sequence,
                body=AgentMessageEventBody(
                    total_tokens=_usage_total_tokens(entry),
                    text=entry.payload.text,
                ),
            ),
        )

    def final_assistant_message(
        self,
        *,
        entry: AgentContextEntry,
    ) -> RuntimeEventDraft:
        if entry.entry_type != AgentContextEntryType.ASSISTANT_MESSAGE:
            raise ValueError("Final assistant event requires assistant_message entry")
        if not isinstance(entry.payload, AgentAssistantMessagePayload):
            raise ValueError("Final assistant event requires AgentAssistantMessagePayload")
        if entry.payload.message_type != AgentAssistantMessageType.FINAL:
            raise ValueError("Final assistant event requires final message")

        return RuntimeEventDraft(
            run_id=entry.run_id,
            type=RuntimeEventType.AGENT_FINAL_ASSISTANT_MESSAGE,
            payload=AgentEventPayload(
                step_id=entry.source_step_id,
                turn_id=entry.payload.turn_id,
                agent_sequence=entry.sequence,
                body=AgentMessageEventBody(
                    total_tokens=_usage_total_tokens(entry),
                    text=entry.payload.text,
                ),
            ),
        )

    def tool_call(
        self,
        *,
        entry: AgentContextEntry,
    ) -> RuntimeEventDraft:
        if entry.entry_type != AgentContextEntryType.TOOL_CALL:
            raise ValueError("Tool call event requires tool_call entry")
        if not isinstance(entry.payload, AgentToolCallPayload):
            raise ValueError("Tool call event requires AgentToolCallPayload")

        return RuntimeEventDraft(
            run_id=entry.run_id,
            type=RuntimeEventType.AGENT_TOOL_CALL,
            payload=AgentEventPayload(
                step_id=entry.source_step_id,
                turn_id=entry.payload.turn_id,
                agent_sequence=entry.sequence,
                body=AgentToolCallEventBody(
                    turn_id=entry.payload.turn_id,
                    parent_sequence=entry.payload.parent_sequence,
                    tool_call_id=entry.payload.tool_call_id,
                    tool=entry.payload.tool,
                    args=entry.payload.args,
                ),
            ),
        )

    def tool_result(
        self,
        *,
        text: str | None,
        entry: AgentContextEntry,
    ) -> RuntimeEventDraft:
        if entry.entry_type != AgentContextEntryType.TOOL_RESULT:
            raise ValueError("Tool result event requires tool_result entry")
        if not isinstance(entry.payload, AgentToolResultPayload):
            raise ValueError("Tool result event requires AgentToolResultPayload")

        return RuntimeEventDraft(
            run_id=entry.run_id,
            type=RuntimeEventType.AGENT_TOOL_RESULT,
            payload=AgentEventPayload(
                step_id=entry.source_step_id,
                turn_id=entry.payload.turn_id,
                agent_sequence=entry.sequence,
                body=AgentToolResultEventBody(
                    turn_id=entry.payload.turn_id,
                    parent_sequence=entry.payload.parent_sequence,
                    tool_call_id=entry.payload.tool_call_id,
                    tool=entry.payload.tool,
                    status=entry.payload.status,
                    data=entry.payload.data,
                    text=text,
                    error=entry.payload.error,
                ),
            ),
        )

    def interrupted(
        self,
        *,
        run_id: str,
        step_id: str,
        turn_id: str,
    ) -> RuntimeEventDraft:
        return RuntimeEventDraft(
            run_id=run_id,
            type=RuntimeEventType.AGENT_INTERRUPTED,
            step_id=step_id,
            step_type="agent",
            payload=AgentLifecyclePayload(
                turn_id=turn_id,
                stop_reason="interrupted",
            ),
        )

    def max_turns_exhausted(
        self,
        *,
        run_id: str,
        step_id: str,
        turn_id: str,
    ) -> RuntimeEventDraft:
        return RuntimeEventDraft(
            run_id=run_id,
            type=RuntimeEventType.AGENT_MAX_TURNS_EXHAUSTED,
            step_id=step_id,
            step_type="agent",
            payload=AgentLifecyclePayload(
                turn_id=turn_id,
                stop_reason="max_turns_exhausted",
            ),
        )


def _usage_total_tokens(entry: AgentContextEntry) -> int:
    if entry.usage is None or entry.usage.total_tokens is None:
        return 0
    return entry.usage.total_tokens
