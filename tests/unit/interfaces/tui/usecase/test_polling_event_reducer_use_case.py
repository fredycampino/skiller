from __future__ import annotations

import pytest

from skiller.interfaces.tui.port.run_port import PollingEvent, PollingEventKind
from skiller.interfaces.tui.usecase.polling_event_reducer_use_case import (
    PollingEventReducerUseCase,
)
from skiller.interfaces.tui.usecase.run_event_context import (
    RunEventContext,
    RunMode,
    RunStatus,
)
from skiller.interfaces.tui.viewmodel.console_screen_state import (
    AgentAssistantMessageItem,
    ConsoleScreenState,
    RunStatusItem,
    RunStepItem,
    ScreenStatus,
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
    assert state.screen_status == ScreenStatus.WAITING
    assert state.waiting_prompt == "Write a message"
    assert context.run_id == "run-1"
    assert context.mode == RunMode.FLOW
    assert context.status == RunStatus.WAITING_INPUT
    assert context.event_ids == {"evt-1"}
    assert len(state.transcript_items) == 1
    assert isinstance(state.transcript_items[0], RunStatusItem)
    assert state.transcript_items[0].status == "waiting"

    use_case.execute(state=state, events=events)

    assert context.event_ids == {"evt-1"}
    assert len(state.transcript_items) == 1


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
    assert context.mode == RunMode.FLOW
    assert context.status == RunStatus.WAITING_INPUT
    assert any(isinstance(item, RunStepItem) for item in state.transcript_items)
    assert state.screen_status == ScreenStatus.WAITING


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
    assert len(state.transcript_items) == 1
    assert isinstance(state.transcript_items[0], AgentAssistantMessageItem)
    assert state.transcript_items[0].message_type == "tool_calls"
    assert state.transcript_items[0].text == "I will inspect the repository state."
