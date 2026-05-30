from skiller.application.agent.config.output_truncator import OutputTruncator
from skiller.application.agent.event.agent_event_truncator import (
    AgentEventOutputPolicy,
    AgentEventTruncator,
)
from skiller.domain.agent.agent_config_model import AgentEventOutputConfig
from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessagePayload,
    AgentAssistantMessageType,
    AgentContextEntry,
    AgentContextEntryType,
    AgentToolCallPayload,
    AgentToolResultPayload,
)
from skiller.domain.event.event_model import (
    AgentBodyToolMessage,
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
        output_truncator: OutputTruncator,
    ) -> None:
        self.runtime_event_store = runtime_event_store
        self.output_truncator = output_truncator

    def emit_assistant_message(
        self,
        *,
        entry: AgentContextEntry,
        config: AgentEventOutputConfig,
    ) -> None:
        if entry.entry_type != AgentContextEntryType.ASSISTANT_MESSAGE:
            raise ValueError("Assistant event requires assistant_message entry")
        if not isinstance(entry.payload, AgentAssistantMessagePayload):
            raise ValueError("Assistant event requires AgentAssistantMessagePayload")
        if entry.payload.message_type != AgentAssistantMessageType.TOOL_CALLS:
            raise ValueError("Assistant event requires tool_calls message")

        truncator = self._truncator(config=config)
        payload = truncator.truncate_assistant_message(entry.payload)
        self.runtime_event_store.append_event(
            RuntimeEventDraft(
                run_id=entry.run_id,
                type=RuntimeEventType.AGENT_ASSISTANT_MESSAGE,
                payload=AgentEventPayload(
                    step_id=entry.source_step_id,
                    turn_id=payload.turn_id,
                    agent_sequence=entry.sequence,
                    body=AgentBodyToolMessage(
                        total_tokens=entry.window_tokens or 0,
                        text=payload.text,
                    ),
                ),
            )
        )

    def emit_final_assistant_message(
        self,
        *,
        entry: AgentContextEntry,
        config: AgentEventOutputConfig,
    ) -> None:
        if entry.entry_type != AgentContextEntryType.ASSISTANT_MESSAGE:
            raise ValueError("Final assistant event requires assistant_message entry")
        if not isinstance(entry.payload, AgentAssistantMessagePayload):
            raise ValueError("Final assistant event requires AgentAssistantMessagePayload")
        if entry.payload.message_type != AgentAssistantMessageType.FINAL:
            raise ValueError("Final assistant event requires final message")

        truncator = self._truncator(config=config)
        payload = truncator.truncate_assistant_message(entry.payload)
        self.runtime_event_store.append_event(
            RuntimeEventDraft(
                run_id=entry.run_id,
                type=RuntimeEventType.AGENT_FINAL_ASSISTANT_MESSAGE,
                payload=AgentEventPayload(
                    step_id=entry.source_step_id,
                    turn_id=payload.turn_id,
                    agent_sequence=entry.sequence,
                    body=AgentBodyToolMessage(
                        total_tokens=entry.window_tokens or 0,
                        text=payload.text,
                    ),
                ),
            )
        )

    def emit_tool_call(
        self,
        *,
        entry: AgentContextEntry,
        config: AgentEventOutputConfig,
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
                    body=self._truncator(config=config).truncate_tool_call(
                        entry.payload,
                    ),
                ),
            )
        )

    def emit_tool_result(
        self,
        *,
        entry: AgentContextEntry,
        config: AgentEventOutputConfig,
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
                    body=self._truncator(config=config).truncate_tool_result(
                        entry.payload,
                    ),
                ),
            )
        )

    def _truncator(self, *, config: AgentEventOutputConfig) -> AgentEventTruncator:
        policy = AgentEventOutputPolicy.from_config(config)
        return AgentEventTruncator(policy, self.output_truncator)

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
