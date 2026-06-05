from dataclasses import dataclass

import pytest

from skiller.application.agent.config.output_truncator import OutputTruncator
from skiller.application.agent.event.agent_event_draft_builder import (
    AgentEventDraftBuilder,
)
from skiller.application.agent.event.agent_event_publisher import AgentEventPublisher
from skiller.domain.agent.agent_config_model import (
    AgentEventOutputConfig,
    AgentEventOutputTruncateConfig,
)
from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessagePayload,
    AgentContextEntry,
    AgentContextEntryType,
    AgentToolCallPayload,
)
from skiller.domain.agent.llm_model import LLMUsage
from skiller.domain.event.event_agent_model import (
    AgentEventPayload,
    AgentMessageEventBody,
    AgentToolCallEventBody,
)
from skiller.domain.event.event_model import (
    RuntimeEventDraft,
    RuntimeEventType,
)
from skiller.domain.event.runtime_event_store_port import RuntimeEventStorePort

pytestmark = pytest.mark.unit


def test_agent_event_publisher_emits_assistant_message_from_context_entry() -> None:
    store = _FakeRuntimeEventStore()
    publisher = AgentEventPublisher(
        store,
        AgentEventDraftBuilder(),
        OutputTruncator(),
    )
    event_output = _event_output(max_text_chars=10)

    publisher.emit_assistant_message(
        entry=AgentContextEntry(
            id="entry-1",
            run_id="run-1",
            context_id="ctx-1",
            sequence=7,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            usage=LLMUsage(total_tokens=2144),
            payload=AgentAssistantMessagePayload(
                turn_id="turn-4",
                message_type="tool_calls",
                text="I will call a tool.",
            ),
            source_step_id="support_agent",
            created_at="2026-05-15T00:00:00Z",
        ),
        config=event_output,
    )

    assert len(store.events) == 1
    event = store.events[0]
    assert event.type == RuntimeEventType.AGENT_ASSISTANT_MESSAGE
    assert event.run_id == "run-1"
    assert isinstance(event.payload, AgentEventPayload)
    assert event.payload.step_id == "support_agent"
    assert event.payload.turn_id == "turn-4"
    assert event.payload.agent_sequence == 7
    assert isinstance(event.payload.body, AgentMessageEventBody)
    assert event.payload.body.total_tokens == 2144
    assert event.payload.body.text == "I will cal..."


def test_agent_event_publisher_emits_final_assistant_message_with_plain_payload() -> None:
    store = _FakeRuntimeEventStore()
    publisher = AgentEventPublisher(
        store,
        AgentEventDraftBuilder(),
        OutputTruncator(),
    )
    event_output = _event_output(max_text_chars=10)

    publisher.emit_final_assistant_message(
        entry=AgentContextEntry(
            id="entry-1",
            run_id="run-1",
            context_id="ctx-1",
            sequence=7,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            usage=LLMUsage(total_tokens=2144),
            payload=AgentAssistantMessagePayload(
                turn_id="turn-4",
                message_type="final",
                text="Final answer is intentionally longer than the event text limit.",
            ),
            source_step_id="support_agent",
            created_at="2026-05-15T00:00:00Z",
        ),
        config=event_output,
    )

    event = store.events[0]
    assert event.type == RuntimeEventType.AGENT_FINAL_ASSISTANT_MESSAGE
    assert isinstance(event.payload, AgentEventPayload)
    assert isinstance(event.payload.body, AgentMessageEventBody)
    assert event.payload.body.total_tokens == 2144
    assert event.payload.body.text == "Final answ..."


def test_agent_event_publisher_emits_agent_lifecycle_events() -> None:
    store = _FakeRuntimeEventStore()
    publisher = AgentEventPublisher(
        store,
        AgentEventDraftBuilder(),
        OutputTruncator(),
    )

    publisher.emit_interrupted(
        run_id="run-1",
        step_id="support_agent",
        turn_id="turn-4",
    )
    publisher.emit_max_turns_exhausted(
        run_id="run-1",
        step_id="support_agent",
        turn_id="turn-5",
    )

    interrupted_event, max_turns_event = store.events

    assert interrupted_event.type == RuntimeEventType.AGENT_INTERRUPTED
    assert interrupted_event.step_id == "support_agent"
    assert interrupted_event.step_type == "agent"
    assert interrupted_event.payload.stop_reason == "interrupted"

    assert max_turns_event.type == RuntimeEventType.AGENT_MAX_TURNS_EXHAUSTED
    assert max_turns_event.step_id == "support_agent"
    assert max_turns_event.step_type == "agent"
    assert max_turns_event.payload.stop_reason == "max_turns_exhausted"


def test_agent_event_publisher_truncates_observable_payloads_before_persistence() -> None:
    store = _FakeRuntimeEventStore()
    publisher = AgentEventPublisher(
        store,
        AgentEventDraftBuilder(),
        OutputTruncator(),
    )
    event_output = AgentEventOutputConfig()

    publisher.emit_tool_call(
        entry=AgentContextEntry(
            id="entry-1",
            run_id="run-1",
            context_id="ctx-1",
            sequence=8,
            entry_type=AgentContextEntryType.TOOL_CALL,
            usage=None,
            payload=AgentToolCallPayload(
                turn_id="turn-4",
                parent_sequence=7,
                tool_call_id="call-1",
                tool="shell",
                args={"command": "x" * 1000},
            ),
            source_step_id="support_agent",
            created_at="2026-05-15T00:00:00Z",
        ),
        config=event_output,
    )

    event = store.events[0]
    payload = event.payload
    assert isinstance(payload, AgentEventPayload)
    assert isinstance(payload.body, AgentToolCallEventBody)
    assert payload.body.args["command"].endswith("...")


@dataclass
class _FakeRuntimeEventStore(RuntimeEventStorePort):
    events: list[RuntimeEventDraft]

    def __init__(self) -> None:
        self.events = []

    def append_event(self, event: RuntimeEventDraft) -> str:
        self.events.append(event)
        return f"event-{len(self.events)}"

    def list_events(
        self,
        run_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ):  # noqa: ANN201
        raise NotImplementedError

    def get_last_event(self, run_id: str):  # noqa: ANN201
        raise NotImplementedError


def _event_output(*, max_text_chars: int) -> AgentEventOutputConfig:
    return AgentEventOutputConfig(
        truncate=AgentEventOutputTruncateConfig(
            max_text_chars=max_text_chars,
        ),
    )
