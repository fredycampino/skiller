from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.text import Text

from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView


@dataclass(frozen=True)
class PlaceholderView(TranscriptView):
    text: str

    def render(self, *, theme: TuiTheme) -> RenderableType:
        return Text(
            self.text,
            style=theme.rich_style(theme.color_text_muted),
        )
