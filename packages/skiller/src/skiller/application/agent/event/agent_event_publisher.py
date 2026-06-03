from skiller.application.agent.config.output_truncator import OutputTruncator
from skiller.application.agent.event.agent_event_draft_builder import (
    AgentEventDraftBuilder,
)
from skiller.application.agent.event.agent_event_truncator import (
    AgentEventOutputPolicy,
    AgentEventTruncator,
)
from skiller.domain.agent.agent_config_model import AgentEventOutputConfig
from skiller.domain.agent.agent_context_model import AgentContextEntry
from skiller.domain.event.event_agent_model import AgentEventPayload
from skiller.domain.event.event_model import RuntimeEventDraft
from skiller.domain.event.runtime_event_store_port import RuntimeEventStorePort


class AgentEventPublisher:
    def __init__(
        self,
        runtime_event_store: RuntimeEventStorePort,
        draft_builder: AgentEventDraftBuilder,
        output_truncator: OutputTruncator,
    ) -> None:
        self.runtime_event_store = runtime_event_store
        self.draft_builder = draft_builder
        self.output_truncator = output_truncator

    def emit_assistant_message(
        self,
        *,
        entry: AgentContextEntry,
        config: AgentEventOutputConfig,
    ) -> None:
        self._append_observable_event(
            self.draft_builder.assistant_message(
                entry=entry,
            ),
            config=config,
        )

    def emit_final_assistant_message(
        self,
        *,
        entry: AgentContextEntry,
        config: AgentEventOutputConfig,
    ) -> None:
        self._append_observable_event(
            self.draft_builder.final_assistant_message(
                entry=entry,
            ),
            config=config,
        )

    def emit_tool_call(
        self,
        *,
        entry: AgentContextEntry,
        config: AgentEventOutputConfig,
    ) -> None:
        self._append_observable_event(
            self.draft_builder.tool_call(
                entry=entry,
            ),
            config=config,
        )

    def emit_tool_result(
        self,
        *,
        text: str | None,
        entry: AgentContextEntry,
        config: AgentEventOutputConfig,
    ) -> None:
        self._append_observable_event(
            self.draft_builder.tool_result(
                text=text,
                entry=entry,
            ),
            config=config,
        )

    def emit_interrupted(
        self,
        *,
        run_id: str,
        step_id: str,
        turn_id: str,
    ) -> None:
        self.runtime_event_store.append_event(
            self.draft_builder.interrupted(
                run_id=run_id,
                step_id=step_id,
                turn_id=turn_id,
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
            self.draft_builder.max_turns_exhausted(
                run_id=run_id,
                step_id=step_id,
                turn_id=turn_id,
            )
        )

    def _append_observable_event(
        self,
        event: RuntimeEventDraft,
        *,
        config: AgentEventOutputConfig,
    ) -> None:
        payload = event.payload
        if not isinstance(payload, AgentEventPayload):
            self.runtime_event_store.append_event(event)
            return

        truncator = AgentEventTruncator(
            AgentEventOutputPolicy.from_config(config),
            self.output_truncator,
        )
        self.runtime_event_store.append_event(
            RuntimeEventDraft(
                run_id=event.run_id,
                type=event.type,
                payload=truncator.truncate_payload(payload),
                step_id=event.step_id,
                step_type=event.step_type,
                agent_sequence=event.agent_sequence,
            )
        )
