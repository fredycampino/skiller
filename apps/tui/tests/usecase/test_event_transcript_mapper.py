from __future__ import annotations

import pytest

from stui.port.event_models import (
    AgentAssistantMessagePayload,
    AgentAssistantMessageType,
    AgentLifecyclePayload,
    AgentStopReason,
    AgentToolCallPayload,
    AgentToolResultPayload,
    AgentToolResultStatus,
    ErrorPayload,
    InputReceivedPayload,
    LogEvent,
    LogEventPayload,
    LogEventType,
    OutputPayload,
    RunWaitingPayload,
    StepStartedPayload,
    StepSuccessPayload,
)
from stui.usecase.event_transcript_mapper import EventTranscriptMapper
from stui.viewmodel.console_screen_state import (
    AgentAssistantMessageItem,
    AgentSystemNoticeItem,
    AgentToolCallItem,
    AgentToolResultItem,
    DispatchErrorItem,
    RunStepItem,
    RunWaitingInputItem,
    UserInputItem,
)

pytestmark = pytest.mark.unit


def test_event_transcript_mapper_renders_agent_tool_turn() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.AGENT_ASSISTANT_MESSAGE,
                step_id="support_agent",
                step_type="agent",
                payload=AgentAssistantMessagePayload(
                    type="assistant_message",
                    turn_id="turn-1",
                    message_type=AgentAssistantMessageType.TOOL_CALLS,
                    text="I will inspect the repository state.",
                ),
            ),
            _event(
                LogEventType.AGENT_TOOL_CALL,
                sequence=2,
                step_id="support_agent",
                step_type="agent",
                payload=AgentToolCallPayload(
                    type="tool_call",
                    turn_id="turn-1",
                    parent_sequence=1,
                    tool_call_id="call-1",
                    tool="shell",
                    args={"command": "git status --short"},
                ),
            ),
            _event(
                LogEventType.AGENT_TOOL_RESULT,
                sequence=3,
                step_id="support_agent",
                step_type="agent",
                payload=AgentToolResultPayload(
                    type="tool_result",
                    turn_id="turn-1",
                    parent_sequence=1,
                    tool_call_id="call-1",
                    tool="shell",
                    status=AgentToolResultStatus.COMPLETED,
                    data={"ok": True, "exit_code": 0},
                    text="Command completed successfully.",
                    error=None,
                ),
            ),
        ],
    )

    assert isinstance(items[0], AgentAssistantMessageItem)
    assert isinstance(items[1], AgentToolCallItem)
    assert isinstance(items[2], AgentToolResultItem)
    assert items[1].command == "git status --short"
    assert items[2].preview == "Command completed successfully."


def test_event_transcript_mapper_uses_step_success_as_agent_final_output() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.AGENT_ASSISTANT_MESSAGE,
                payload=AgentAssistantMessagePayload(
                    type="assistant_message",
                    turn_id="turn-1",
                    message_type=AgentAssistantMessageType.FINAL,
                    text="Hecho truncado...",
                ),
            ),
            _event(
                LogEventType.STEP_SUCCESS,
                sequence=2,
                step_id="support_agent",
                step_type="agent",
                payload=StepSuccessPayload(
                    output=OutputPayload(
                        text="Hecho completo.",
                        value={"data": {"final": {"text": "Hecho completo."}}},
                        body_ref=None,
                    )
                ),
            ),
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], AgentAssistantMessageItem)
    assert items[0].message_type == "final"
    assert items[0].text == "Hecho completo."


def test_event_transcript_mapper_renders_input_received() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.INPUT_RECEIVED,
                payload=InputReceivedPayload(payload={"text": "hola mundo"}),
            )
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], UserInputItem)
    assert items[0].text == "hola mundo"


def test_event_transcript_mapper_orders_events_by_created_at_and_sequence() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.INPUT_RECEIVED,
                sequence=3,
                payload=InputReceivedPayload(payload={"text": "third"}),
                created_at="2026-05-12T10:30:16Z",
            ),
            _event(
                LogEventType.INPUT_RECEIVED,
                sequence=2,
                payload=InputReceivedPayload(payload={"text": "second"}),
                created_at="2026-05-12T10:30:15Z",
            ),
            _event(
                LogEventType.INPUT_RECEIVED,
                sequence=1,
                payload=InputReceivedPayload(payload={"text": "first"}),
                created_at="2026-05-12T10:30:15Z",
            ),
        ],
    )

    assert [item.text for item in items if isinstance(item, UserInputItem)] == [
        "first",
        "second",
        "third",
    ]


def test_event_transcript_mapper_renders_agent_interrupted_notice_and_skips_step_success() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.AGENT_INTERRUPTED,
                step_id="support_agent",
                step_type="agent",
                payload=AgentLifecyclePayload(
                    turn_id="turn-7",
                    stop_reason=AgentStopReason.INTERRUPTED,
                ),
            ),
            _event(
                LogEventType.STEP_SUCCESS,
                sequence=2,
                step_id="support_agent",
                step_type="agent",
                payload=StepSuccessPayload(
                    output=OutputPayload(
                        text="",
                        value={"data": {"stop_reason": "interrupted"}},
                        body_ref=None,
                    )
                ),
            ),
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], AgentSystemNoticeItem)
    assert items[0].text == "Interrupted by user"


def test_event_transcript_mapper_renders_waiting_output() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.STEP_STARTED,
                step_id="ask_user",
                step_type="wait_input",
                payload=StepStartedPayload(),
            ),
            _event(
                LogEventType.RUN_WAITING,
                sequence=2,
                step_id="ask_user",
                step_type="wait_input",
                payload=RunWaitingPayload(
                    output=OutputPayload(
                        text="Write a message.",
                        value={"prompt": "Write a message.", "payload": None},
                        body_ref=None,
                    )
                ),
            ),
        ],
    )

    assert len(items) == 2
    assert isinstance(items[0], RunStepItem)
    assert isinstance(items[1], RunWaitingInputItem)
    assert items[1].step_type == "wait_input"
    assert items[1].step_id == "ask_user"
    assert items[1].prompt == "Write a message."


def test_event_transcript_mapper_surfaces_observer_loop_error() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.OBSERVER_LOOP_ERROR,
                payload=ErrorPayload(error="RuntimeError: boom"),
            )
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], DispatchErrorItem)
    assert items[0].message == "RuntimeError: boom"


def _event(
    event_type: LogEventType,
    *,
    sequence: int = 1,
    step_id: str | None = None,
    step_type: str | None = None,
    created_at: str = "2026-05-12T10:30:15Z",
    payload: LogEventPayload,
) -> LogEvent:
    return LogEvent(
        sequence=sequence,
        event_id=f"evt-{sequence}",
        run_id="run-1",
        event_type=event_type,
        step_id=step_id,
        step_type=step_type,
        agent_sequence=None,
        created_at=created_at,
        payload=payload,
    )
