from __future__ import annotations

import pytest
from stui.port.run_port import PollingEvent, PollingEventKind
from stui.usecase.polling_event_reducer_use_case import (
    PollingEventReducerUseCase,
)
from stui.usecase.run_event_context import (
    RunEventContext,
    RunStatus,
)
from stui.viewmodel.console_screen_state import (
    AgentAssistantMessageItem,
    AgentSystemNoticeItem,
    ConsoleScreenState,
    OutputFormat,
    PromptMode,
    RunOutputItem,
    RunStatusItem,
    RunStepItem,
    TranscriptMode,
    UserInputItem,
    ViewStatusKind,
)

pytestmark = pytest.mark.unit


def test_polling_event_reducer_keeps_waiting_context_and_dedupes_event_ids() -> None:
    state = ConsoleScreenState()
    context = RunEventContext()
    use_case = PollingEventReducerUseCase(context=context)
    events = [
        PollingEvent(
            kind=PollingEventKind.LOG,
            run_id="run-1",
            event_type="RUN_WAITING",
            step="ask_user",
            step_type="wait_input",
            output="Write a message",
            event_id="evt-1",
        ),
        PollingEvent(
            kind=PollingEventKind.STATUS,
            run_id="run-1",
            status="WAITING",
        ),
    ]

    result = use_case.execute(state=state, events=events)

    assert result.state is state
    assert state.view_status.kind == ViewStatusKind.WAITING
    assert state.prompt.waiting_prompt == "Write a message"
    assert state.prompt.mode == PromptMode.CHAT
    assert context.run_id == "run-1"
    assert context.status == RunStatus.WAITING_INPUT
    assert context.event_ids == {"evt-1"}
    assert len(state.transcript.items) == 1
    assert isinstance(state.transcript.items[0], RunStatusItem)
    assert state.transcript.items[0].status == "waiting"

    use_case.execute(state=state, events=events)

    assert context.event_ids == {"evt-1"}
    assert len(state.transcript.items) == 1


def test_polling_event_reducer_keeps_waiting_step_context_from_step_started() -> None:
    state = ConsoleScreenState()
    context = RunEventContext()
    use_case = PollingEventReducerUseCase(context=context)

    use_case.execute(
        state=state,
        events=[
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-2",
                event_type="STEP_STARTED",
                step="ask_user",
                step_type="wait_input",
                event_id="evt-2",
            ),
            PollingEvent(
                kind=PollingEventKind.STATUS,
                run_id="run-2",
                status="WAITING",
            ),
        ],
    )

    assert context.run_id == "run-2"
    assert context.status == RunStatus.WAITING_INPUT
    assert any(isinstance(item, RunStepItem) for item in state.transcript.items)
    assert state.view_status.kind == ViewStatusKind.WAITING


def test_polling_event_reducer_appends_agent_assistant_message() -> None:
    state = ConsoleScreenState()
    context = RunEventContext()
    use_case = PollingEventReducerUseCase(context=context)

    result = use_case.execute(
        state=state,
        events=[
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1",
                event_type="AGENT_ASSISTANT_MESSAGE",
                step="support_agent",
                step_type="agent",
                message_type="tool_calls",
                assistant_text="I will inspect the repository state.",
                event_id="evt-agent-assistant",
            ),
        ],
    )

    assert result.state is state
    assert len(state.transcript.items) == 1
    assert isinstance(state.transcript.items[0], AgentAssistantMessageItem)
    assert state.transcript.items[0].message_type == "tool_calls"
    assert state.transcript.items[0].text == "I will inspect the repository state."
    assert state.transcript.mode == TranscriptMode.CHAT


def test_polling_event_reducer_ignores_agent_final_message_event() -> None:
    state = ConsoleScreenState()
    context = RunEventContext()
    use_case = PollingEventReducerUseCase(context=context)

    result = use_case.execute(
        state=state,
        events=[
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1",
                event_type="AGENT_ASSISTANT_MESSAGE",
                step="support_agent",
                step_type="agent",
                message_type="final",
                assistant_text="Hecho.",
                event_id="evt-agent-final",
            ),
        ],
    )

    assert result.state is state
    assert state.transcript.items == []
    assert state.transcript.mode == TranscriptMode.CHAT


def test_polling_event_reducer_uses_step_success_as_agent_final_output() -> None:
    state = ConsoleScreenState()
    context = RunEventContext()
    use_case = PollingEventReducerUseCase(context=context)

    result = use_case.execute(
        state=state,
        events=[
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1",
                event_type="AGENT_ASSISTANT_MESSAGE",
                step="support_agent",
                step_type="agent",
                message_type="final",
                assistant_text="Hecho truncado...",
                event_id="evt-agent-final",
            ),
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1",
                event_type="STEP_SUCCESS",
                step="support_agent",
                step_type="agent",
                output='{"text":"Hecho completo."}',
                event_id="evt-agent-step-success",
            ),
        ],
    )

    assert result.state is state
    assert len(state.transcript.items) == 1
    assert isinstance(state.transcript.items[0], RunOutputItem)
    assert state.transcript.items[0].output == '{"text":"Hecho completo."}'
    assert state.transcript.items[0].format == OutputFormat.MARKDOWN
    assert state.transcript.mode == TranscriptMode.CHAT


def test_polling_event_reducer_reconstructs_user_input_from_input_received() -> None:
    state = ConsoleScreenState()
    context = RunEventContext()
    use_case = PollingEventReducerUseCase(context=context)

    result = use_case.execute(
        state=state,
        events=[
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1",
                event_type="INPUT_RECEIVED",
                user_input_text="hola mundo",
                event_id="evt-input-received",
            ),
        ],
    )

    assert result.state is state
    assert len(state.transcript.items) == 1
    assert isinstance(state.transcript.items[0], UserInputItem)
    assert state.transcript.items[0].text == "hola mundo"


def test_polling_event_reducer_appends_agent_interrupted_notice() -> None:
    state = ConsoleScreenState()
    context = RunEventContext()
    use_case = PollingEventReducerUseCase(context=context)

    result = use_case.execute(
        state=state,
        events=[
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1",
                event_type="AGENT_INTERRUPTED",
                step="support_agent",
                step_type="agent",
                turn_id="turn-7",
                event_id="evt-agent-interrupted",
            ),
        ],
    )

    assert result.state is state
    assert len(state.transcript.items) == 1
    assert isinstance(state.transcript.items[0], AgentSystemNoticeItem)
    assert state.transcript.items[0].text == "Interrupted by user"
    assert state.transcript.mode == TranscriptMode.CHAT


def test_polling_event_reducer_appends_agent_max_turns_notice() -> None:
    state = ConsoleScreenState()
    context = RunEventContext()
    use_case = PollingEventReducerUseCase(context=context)

    result = use_case.execute(
        state=state,
        events=[
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1",
                event_type="AGENT_MAX_TURNS_EXHAUSTED",
                step="support_agent",
                step_type="agent",
                turn_id="turn-9",
                event_id="evt-agent-max-turns",
            ),
        ],
    )

    assert result.state is state
    assert len(state.transcript.items) == 1
    assert isinstance(state.transcript.items[0], AgentSystemNoticeItem)
    assert state.transcript.items[0].text == "Turn limit reached"
    assert state.transcript.mode == TranscriptMode.CHAT


def test_polling_event_reducer_skips_agent_step_success_after_interrupted_notice() -> None:
    state = ConsoleScreenState()
    context = RunEventContext()
    use_case = PollingEventReducerUseCase(context=context)

    result = use_case.execute(
        state=state,
        events=[
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1",
                event_type="AGENT_INTERRUPTED",
                step="support_agent",
                step_type="agent",
                turn_id="turn-7",
                event_id="evt-agent-interrupted",
            ),
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1",
                event_type="STEP_SUCCESS",
                step="support_agent",
                step_type="agent",
                output=(
                    '{"text":"","value":{"data":{"context_id":"ctx-1","final":null,'
                    '"turn_count":1,"tool_call_count":0,"stop_reason":"interrupted"}}}'
                ),
                event_id="evt-agent-step-success",
            ),
        ],
    )

    assert result.state is state
    assert len(state.transcript.items) == 1
    assert isinstance(state.transcript.items[0], AgentSystemNoticeItem)
    assert state.transcript.items[0].text == "Interrupted by user"
