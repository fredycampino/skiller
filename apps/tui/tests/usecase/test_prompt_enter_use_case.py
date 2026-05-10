from __future__ import annotations

import pytest
from stui.usecase.prompt_enter_use_case import PromptEnterUseCase
from stui.viewmodel.console_screen_state import (
    CompletionItem,
    CompletionState,
    ConsoleScreenState,
    PromptState,
)

pytestmark = pytest.mark.unit


def test_prompt_enter_use_case_applies_visible_completion() -> None:
    state = ConsoleScreenState(
        prompt=PromptState(
            text="/ru",
            cursor_position=3,
        )
    )
    state.autocompletion = CompletionState(
        visible=True,
        query="/ru",
        items=(
            CompletionItem(label="run", insert_text="/run"),
            CompletionItem(label="runs", insert_text="/runs"),
        ),
        selected_index=1,
        replace_from=0,
        replace_to=3,
    )
    use_case = PromptEnterUseCase()

    result = use_case.execute(state=state)

    assert result.should_submit is False
    assert result.submit_text == ""
    assert result.state is state
    assert state.prompt.text == "/runs "
    assert state.prompt.cursor_position == 6
    assert state.autocompletion is None


def test_prompt_enter_use_case_requests_submit_when_no_completion() -> None:
    state = ConsoleScreenState(
        prompt=PromptState(
            text="/run chat",
            cursor_position=9,
        )
    )
    use_case = PromptEnterUseCase()

    result = use_case.execute(state=state)

    assert result.should_submit is True
    assert result.submit_text == "/run chat"
    assert result.state is state
    assert state.prompt.text == "/run chat"
    assert state.prompt.cursor_position == 9
    assert state.autocompletion is None
