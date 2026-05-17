from __future__ import annotations

from dataclasses import dataclass, field

from rich.console import RenderableType
from rich.text import Text

from stui.screen.strings import DEFAULT_TUI_STRINGS, TuiStrings
from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView


@dataclass(frozen=True)
class IntroView(TranscriptView):
    strings: TuiStrings = field(default=DEFAULT_TUI_STRINGS)

    def render(self, *, theme: TuiTheme) -> RenderableType:
        return Text(
            f"{self.strings.intro_title}\n"
            f"{self.strings.intro_body}\n"
            f"{self.strings.intro_hint}",
            style=theme.color_text_muted,
        )
