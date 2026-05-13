from __future__ import annotations

import pytest

from stui.usecase.move_completion_use_case import (
    MoveCompletionUseCase,
)
from stui.viewmodel.console_screen_state import (
    CompletionItem,
    CompletionState,
)

pytestmark = pytest.mark.unit


def test_move_completion_use_case_moves_selected_index() -> None:
    use_case = MoveCompletionUseCase()
    completion = CompletionState(
        visible=True,
        query="/ru",
        items=(
            CompletionItem(label="run"),
            CompletionItem(label="runs"),
        ),
        selected_index=0,
        replace_from=0,
        replace_to=3,
    )

    result = use_case.execute(completion=completion, delta=1)

    assert result is not None
    assert result.selected_index == 1
    assert result.selected_item is not None
    assert result.selected_item.label == "runs"


def test_move_completion_use_case_returns_none_when_invisible() -> None:
    use_case = MoveCompletionUseCase()
    completion = CompletionState(
        visible=False,
        query="/ru",
        items=(CompletionItem(label="run"),),
        selected_index=0,
        replace_from=0,
        replace_to=3,
    )

    assert use_case.execute(completion=completion, delta=1) is None
    assert use_case.execute(completion=None, delta=1) is None
