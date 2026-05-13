from __future__ import annotations

import pytest

from stui.usecase.project_transcript_use_case import (
    ProjectTranscriptUseCase,
)
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    RunOutputItem,
    RunResumeItem,
    RunStepItem,
    TranscriptMode,
    UserInputItem,
)

pytestmark = pytest.mark.unit


def test_project_transcript_use_case_keeps_all_items_in_flow_mode() -> None:
    state = ConsoleScreenState(session_key="main")
    state.transcript.items.extend(
        [
            UserInputItem(text="hola"),
            RunResumeItem(run_id="run-1", skill="agent_tools"),
            RunStepItem(run_id="run-1", step_type="switch", step_id="decide_exit"),
        ]
    )

    visible_items = ProjectTranscriptUseCase().execute(state=state)

    assert visible_items == state.transcript.items


def test_project_transcript_use_case_hides_resume_and_non_agent_flow_items_in_chat_mode(
) -> None:
    state = ConsoleScreenState(session_key="main")
    state.transcript.mode = TranscriptMode.CHAT
    state.transcript.items.extend(
        [
            UserInputItem(text="hola"),
            RunResumeItem(run_id="run-1", skill="agent_tools"),
            RunStepItem(run_id="run-1", step_type="switch", step_id="decide_exit"),
            RunOutputItem(
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
        RunStepItem(run_id="run-1", step_type="agent", step_id="support_agent"),
    ]
