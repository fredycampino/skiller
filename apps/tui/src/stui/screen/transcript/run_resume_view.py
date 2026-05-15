from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.text import Text

from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView
from stui.viewmodel.console_screen_state import RunResumeItem


@dataclass(frozen=True)
class RunResumeView(TranscriptView):
    item: RunResumeItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        return Text(
            f"\u21b3 resume({self.item.skill})",
            style=theme.rich_style(theme.color_text_muted),
        )
