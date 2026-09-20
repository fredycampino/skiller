from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.text import Text

from stui.screen.theme import TuiTheme
from stui.screen.transcript.item_view import TranscriptItemView
from stui.viewmodel.console_screen_state import RunWaitingInputItem


@dataclass(frozen=True)
class RunWaitingInputView(TranscriptItemView):
    item: RunWaitingInputItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        return Text(
            "   ...",
            style=theme.color_text_muted,
        )
