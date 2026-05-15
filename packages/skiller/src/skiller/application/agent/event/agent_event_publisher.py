from skiller.application.agent.event.agent_event_truncator import AgentEventTruncator
from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessagePayload,
    AgentContextEntry,
    AgentContextEntryType,
    AgentToolCallPayload,
    AgentToolResultPayload,
)
from skiller.domain.event.event_model import (
    AgentEventPayload,
    AgentLifecyclePayload,
    RuntimeEventDraft,
    RuntimeEventType,
)
from skiller.domain.event.runtime_event_store_port import RuntimeEventStorePort


class AgentEventPublisher:
    def __init__(
        self,
        runtime_event_store: RuntimeEventStorePort,
        truncator: AgentEventTruncator,
    ) -> None:
        self.runtime_event_store = runtime_event_store
        self.truncator = truncator

    def emit_assistant_message(
        self,
        *,
        entry: AgentContextEntry,
    ) -> None:
        if entry.entry_type != AgentContextEntryType.ASSISTANT_MESSAGE:
            raise ValueError("Assistant event requires assistant_message entry")
        if not isinstance(entry.payload, AgentAssistantMessagePayload):
            raise ValueError("Assistant event requires AgentAssistantMessagePayload")

        self.runtime_event_store.append_event(
            RuntimeEventDraft(
                run_id=entry.run_id,
                type=RuntimeEventType.AGENT_ASSISTANT_MESSAGE,
                payload=AgentEventPayload(
                    step_id=entry.source_step_id,
                    turn_id=entry.payload.turn_id,
                    agent_sequence=entry.sequence,
                    body=self.truncator.truncate_assistant_message(entry.payload),
                ),
            )
        )

    def emit_tool_call(
        self,
        *,
        entry: AgentContextEntry,
    ) -> None:
        if entry.entry_type != AgentContextEntryType.TOOL_CALL:
            raise ValueError("Tool call event requires tool_call entry")
        if not isinstance(entry.payload, AgentToolCallPayload):
            raise ValueError("Tool call event requires AgentToolCallPayload")

        self.runtime_event_store.append_event(
            RuntimeEventDraft(
                run_id=entry.run_id,
                type=RuntimeEventType.AGENT_TOOL_CALL,
                payload=AgentEventPayload(
                    step_id=entry.source_step_id,
                    turn_id=entry.payload.turn_id,
                    agent_sequence=entry.sequence,
                    body=self.truncator.truncate_tool_call(entry.payload),
                ),
            )
        )

    def emit_tool_result(
        self,
        *,
        entry: AgentContextEntry,
    ) -> None:
        if entry.entry_type != AgentContextEntryType.TOOL_RESULT:
            raise ValueError("Tool result event requires tool_result entry")
        if not isinstance(entry.payload, AgentToolResultPayload):
            raise ValueError("Tool result event requires AgentToolResultPayload")

        self.runtime_event_store.append_event(
            RuntimeEventDraft(
                run_id=entry.run_id,
                type=RuntimeEventType.AGENT_TOOL_RESULT,
                payload=AgentEventPayload(
                    step_id=entry.source_step_id,
                    turn_id=entry.payload.turn_id,
                    agent_sequence=entry.sequence,
                    body=self.truncator.truncate_tool_result(entry.payload),
                ),
            )
        )

    def emit_interrupted(
        self,
        *,
        run_id: str,
        step_id: str,
        turn_id: str,
    ) -> None:
        self.runtime_event_store.append_event(
            RuntimeEventDraft(
                run_id=run_id,
                type=RuntimeEventType.AGENT_INTERRUPTED,
                step_id=step_id,
                step_type="agent",
                payload=AgentLifecyclePayload(
                    turn_id=turn_id,
                    stop_reason="interrupted",
                ),
            )
        )

    def emit_max_turns_exhausted(
        self,
        *,
        run_id: str,
        step_id: str,
        turn_id: str,
    ) -> None:
        self.runtime_event_store.append_event(
            RuntimeEventDraft(
                run_id=run_id,
                type=RuntimeEventType.AGENT_MAX_TURNS_EXHAUSTED,
                step_id=step_id,
                step_type="agent",
                payload=AgentLifecyclePayload(
                    turn_id=turn_id,
                    stop_reason="max_turns_exhausted",
                ),
            )
        )
