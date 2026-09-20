from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.text import Text

from stui.screen.theme import TuiTheme
from stui.screen.transcript.item_view import TranscriptItemView


@dataclass(frozen=True)
class PlaceholderView(TranscriptItemView):
    text: str

    def render(self, *, theme: TuiTheme) -> RenderableType:
        return Text(
            self.text,
            style=theme.color_text_muted,
        )
