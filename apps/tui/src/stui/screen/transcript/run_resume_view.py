from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.text import Text

from stui.screen.theme import TuiTheme
from stui.screen.transcript.item_view import TranscriptItemView
from stui.viewmodel.console_screen_state import RunResumeItem


@dataclass(frozen=True)
class RunResumeView(TranscriptItemView):
    item: RunResumeItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        return Text(
            f"\u21b3 resume({self.item.skill})",
            style=theme.color_text_muted,
        )
