from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.padding import Padding
from rich.text import Text

from stui.di.strings import TuiStrings
from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView


@dataclass(frozen=True)
class IntroView(TranscriptView):
    strings: TuiStrings

    def render(self, *, theme: TuiTheme) -> RenderableType:
        intro = Text()
        intro.append(f"{self.strings.intro_title}\n", style=theme.color_text_accent)
        intro.append(f"{self.strings.intro_body}\n", style=theme.color_text_primary)
        intro.append(self.strings.intro_hint, style=theme.color_text_muted)
        return Padding(
            intro,
            (0, 0, 1, 0),
        )
