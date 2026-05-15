from __future__ import annotations

from typing import Protocol

from rich.console import RenderableType

from stui.screen.theme import TuiTheme


class TranscriptView(Protocol):
    def render(self, *, theme: TuiTheme) -> RenderableType: ...
