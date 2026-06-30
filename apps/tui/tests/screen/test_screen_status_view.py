from __future__ import annotations

import pytest
from rich.text import Text

from stui.screen.screen_status_view import ScreenStatusView
from stui.viewmodel.console_screen_state import (
    ViewStatusKind,
    ViewStatusState,
)

pytestmark = pytest.mark.unit



def test_screen_status_view_renders_waiting_with_prompt_in_brackets() -> None:
    view = ScreenStatusView()
    view._state = ViewStatusState(kind=ViewStatusKind.WAITING)
    view._state.message = "Write a message. Type exit, quit, or bye to stop."
    renderable = view.render()

    assert isinstance(renderable, Text)
    assert renderable.plain == "... [Write a message. Type exit, quit, or bye to stop.]"


def test_screen_status_view_renders_waiting_without_prompt() -> None:
    view = ScreenStatusView()
    view._state = ViewStatusState(kind=ViewStatusKind.WAITING)
    view._state.message = ""
    renderable = view.render()

    assert isinstance(renderable, Text)
    assert renderable.plain == "..."
