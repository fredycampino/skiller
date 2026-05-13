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
from stui.usecase.log_event_reducer_use_case import LogEventReducerUseCase
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus
from stui.viewmodel.console_screen_state import (
    AgentAssistantMessageItem,
    AgentSystemNoticeItem,
    AgentToolCallItem,
    AgentToolResultItem,
    ConsoleScreenState,
    DispatchErrorItem,
    OutputFormat,
    RunOutputItem,
    RunStepItem,
    TranscriptMode,
    UserInputItem,
    ViewStatusKind,
)

pytestmark = pytest.mark.unit


def test_log_event_reducer_renders_agent_tool_turn() -> None:
    state = ConsoleScreenState()
    context = _context(mode=RunMode.CHAT)
    use_case = LogEventReducerUseCase(context=context)

    use_case.execute(
        state=state,
        events=[
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

    assert isinstance(state.transcript.items[0], AgentAssistantMessageItem)
    assert isinstance(state.transcript.items[1], AgentToolCallItem)
    assert isinstance(state.transcript.items[2], AgentToolResultItem)
    assert state.transcript.items[1].command == "git status --short"
    assert state.transcript.items[2].preview == "Command completed successfully."
    assert state.transcript.mode == TranscriptMode.CHAT


def test_log_event_reducer_uses_step_success_as_agent_final_output() -> None:
    state = ConsoleScreenState()
    context = _context(mode=RunMode.CHAT)
    use_case = LogEventReducerUseCase(context=context)

    use_case.execute(
        state=state,
        events=[
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

    assert len(state.transcript.items) == 1
    assert isinstance(state.transcript.items[0], RunOutputItem)
    assert state.transcript.items[0].output == (
        '{"text":"Hecho completo.","value":{"data":{"final":{"text":"Hecho completo."}}},'
        '"body_ref":null}'
    )
    assert state.transcript.items[0].format == OutputFormat.MARKDOWN


def test_log_event_reducer_renders_input_received() -> None:
    state = ConsoleScreenState()
    context = _context()
    use_case = LogEventReducerUseCase(context=context)

    use_case.execute(
        state=state,
        events=[
            _event(
                LogEventType.INPUT_RECEIVED,
                payload=InputReceivedPayload(payload={"text": "hola mundo"}),
            )
        ],
    )

    assert len(state.transcript.items) == 1
    assert isinstance(state.transcript.items[0], UserInputItem)
    assert state.transcript.items[0].text == "hola mundo"


def test_log_event_reducer_renders_agent_interrupted_notice_and_skips_step_success() -> None:
    state = ConsoleScreenState()
    context = _context(mode=RunMode.CHAT)
    use_case = LogEventReducerUseCase(context=context)

    use_case.execute(
        state=state,
        events=[
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

    assert len(state.transcript.items) == 1
    assert isinstance(state.transcript.items[0], AgentSystemNoticeItem)
    assert state.transcript.items[0].text == "Interrupted by user"


def test_log_event_reducer_waiting_input_sets_prompt() -> None:
    state = ConsoleScreenState()
    context = _context()
    use_case = LogEventReducerUseCase(context=context)

    use_case.execute(
        state=state,
        events=[
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

    assert isinstance(state.transcript.items[0], RunStepItem)
    assert state.view_status.kind == ViewStatusKind.WAITING
    assert state.prompt.waiting_prompt == "Write a message."
    assert context.status == RunStatus.WAITING_INPUT


def test_log_event_reducer_surfaces_observer_loop_error() -> None:
    state = ConsoleScreenState()
    context = _context()
    use_case = LogEventReducerUseCase(context=context)

    use_case.execute(
        state=state,
        events=[
            _event(
                LogEventType.OBSERVER_LOOP_ERROR,
                payload=ErrorPayload(error="RuntimeError: boom"),
            )
        ],
    )

    assert len(state.transcript.items) == 1
    assert isinstance(state.transcript.items[0], DispatchErrorItem)
    assert state.transcript.items[0].message == "RuntimeError: boom"
    assert state.view_status.kind == ViewStatusKind.ERROR
    assert state.view_status.message == "Observer error"


def _context(*, mode: RunMode = RunMode.FLOW) -> RunEventContext:
    return RunEventContext(
        run_id="",
        skill_name="",
        mode=mode,
        status=RunStatus.RUNNING,
    )


def _event(
    event_type: LogEventType,
    *,
    sequence: int = 1,
    step_id: str | None = None,
    step_type: str | None = None,
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
        created_at="2026-05-12T10:30:15Z",
        payload=payload,
    )
