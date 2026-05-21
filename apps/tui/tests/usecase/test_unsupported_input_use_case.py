from __future__ import annotations

import pytest

from stui.di.strings import TuiStrings
from stui.usecase.unsupported_input_use_case import UnsupportedInputUseCase
from stui.viewmodel.console_screen_state import (
    CompletionItem,
    CompletionState,
    ConsoleScreenState,
    InfoItem,
    PromptMode,
    UserInputItem,
    ViewStatusKind,
)

pytestmark = pytest.mark.unit


def test_unsupported_input_use_case_resets_prompt_status_and_records_message() -> None:
    strings = TuiStrings(unsupported_input_message="Use /run <skill>.")
    use_case = UnsupportedInputUseCase(strings=strings)
    state = ConsoleScreenState(session_key="main")
    state.set_prompt(
        text="hola",
        cursor_position=4,
        waiting_prompt="Write a message",
        mode=PromptMode.AUTOCOMPLETION,
    )
    state.set_status(kind=ViewStatusKind.RUNNING, message="Running")
    state.set_autocompletion(
        CompletionState(
            visible=True,
            query="/r",
            items=(CompletionItem(label="run", insert_text="/run"),),
            selected_index=0,
            replace_from=0,
            replace_to=2,
        )
    )

    result = use_case.execute(state=state, text="hola")

    assert result.state is state
    assert state.prompt.text == ""
    assert state.prompt.cursor_position == 0
    assert state.prompt.waiting_prompt == ""
    assert state.prompt.mode == PromptMode.DEFAULT
    assert state.autocompletion is None
    assert state.view_status.kind == ViewStatusKind.HIDDEN
    assert state.view_status.message == ""
    assert state.transcript.items == [
        UserInputItem(text="hola"),
        InfoItem(text="Use /run <skill>."),
    ]
