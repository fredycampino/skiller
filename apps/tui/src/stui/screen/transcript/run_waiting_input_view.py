from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.text import Text

from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView
from stui.viewmodel.console_screen_state import RunWaitingInputItem


@dataclass(frozen=True)
class RunWaitingInputView(TranscriptView):
    item: RunWaitingInputItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        return Text(
            "   ...",
            style=theme.rich_style(theme.color_text_muted),
        )
