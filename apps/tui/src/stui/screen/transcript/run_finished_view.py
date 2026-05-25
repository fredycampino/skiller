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
        if self.item.status == "error":
            return Text("  failed", style=theme.color_text_muted)
        return Text("  succeeded", style=theme.color_text_muted)
