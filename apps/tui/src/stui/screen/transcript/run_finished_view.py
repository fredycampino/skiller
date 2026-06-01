from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.text import Text

from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView
from stui.viewmodel.console_screen_state import RunFinishedItem


@dataclass(frozen=True)
class RunFinishedView(TranscriptView):
    item: RunFinishedItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        text = Text(style=theme.color_text_muted)
        if self.item.status == "error":
            text.append("  failed")
        else:
            text.append("  succeeded")
        if self.item.action is not None:
            text.append(f"\n  {self.item.action.type} {self.item.action.label}")
        return text
