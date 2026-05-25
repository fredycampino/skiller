from __future__ import annotations

import pytest

from stui.usecase.project_transcript_use_case import (
    ProjectTranscriptUseCase,
)
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    NotifyActionDoneItem,
    RunResumeItem,
    RunStepItem,
    StepNotifyActionItem,
    StepNotifyOutputItem,
    StepOutputItem,
    TranscriptMode,
    UserInputItem,
)

pytestmark = pytest.mark.unit


def test_project_transcript_use_case_keeps_all_items_in_flow_mode() -> None:
    state = ConsoleScreenState(session_key="main")
    state.transcript.mode = TranscriptMode.FLOW
    state.transcript.items.extend(
        [
            UserInputItem(text="hola"),
            RunResumeItem(run_id="run-1", skill="agent_tools"),
            RunStepItem(run_id="run-1", step_type="switch", step_id="decide_exit"),
        ]
    )

    visible_items = ProjectTranscriptUseCase().execute(state=state)

    assert visible_items == state.transcript.items


def test_project_transcript_use_case_hides_notify_action_items() -> None:
    state = ConsoleScreenState(session_key="main")
    state.transcript.mode = TranscriptMode.FLOW
    user_input = UserInputItem(text="hola")
    state.transcript.items.extend(
        [
            user_input,
            StepNotifyActionItem(
                run_id="run-1",
                step_id="auth_link",
                step_type="notify",
                message="Authorize the app",
                action_type="open_url",
                label="Open authorization",
                url="https://example.com/oauth/start",
                status="pending",
            ),
            NotifyActionDoneItem(
                run_id="run-1",
                step_id="auth_link",
                step_type="notify",
                action_type="open_url",
                status="done",
            ),
        ]
    )

    visible_items = ProjectTranscriptUseCase().execute(state=state)

    assert visible_items == [user_input]


def test_project_transcript_use_case_hides_resume_and_conditionals_in_chat_mode(
) -> None:
    state = ConsoleScreenState(session_key="main")
    state.transcript.mode = TranscriptMode.CHAT
    state.transcript.items.extend(
        [
            UserInputItem(text="hola"),
            RunResumeItem(run_id="run-1", skill="agent_tools"),
            RunStepItem(run_id="run-1", step_type="notify", step_id="intro"),
            StepNotifyOutputItem(
                run_id="run-1",
                step_type="notify",
                message="Hello",
            ),
            RunStepItem(run_id="run-1", step_type="assign", step_id="prepare"),
            StepOutputItem(
                run_id="run-1",
                step_type="assign",
                output="Values assigned.",
            ),
            RunStepItem(run_id="run-1", step_type="switch", step_id="decide_exit"),
            StepOutputItem(
                run_id="run-1",
                step_type="switch",
                output='{"text":"Route selected: support_agent."}',
            ),
            RunStepItem(run_id="run-1", step_type="agent", step_id="support_agent"),
        ]
    )

    visible_items = ProjectTranscriptUseCase().execute(state=state)

    assert visible_items == [
        UserInputItem(text="hola"),
        RunStepItem(run_id="run-1", step_type="notify", step_id="intro"),
        StepNotifyOutputItem(
            run_id="run-1",
            step_type="notify",
            message="Hello",
        ),
        RunStepItem(run_id="run-1", step_type="assign", step_id="prepare"),
        StepOutputItem(
            run_id="run-1",
            step_type="assign",
            output="Values assigned.",
        ),
        RunStepItem(run_id="run-1", step_type="agent", step_id="support_agent"),
    ]
