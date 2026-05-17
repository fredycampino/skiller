from __future__ import annotations

from dataclasses import dataclass

from rich.console import Group, RenderableType
from rich.padding import Padding
from rich.text import Text

from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView
from stui.screen.transcript.view_helpers import strip_error_prefix
from stui.viewmodel.console_screen_state import DispatchErrorItem


@dataclass(frozen=True)
class DispatchErrorView(TranscriptView):
    item: DispatchErrorItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        error_style = theme.color_text_error
        return Group(
            Text("error:", style=error_style),
            Padding(
                Text(strip_error_prefix(self.item.message), style=error_style),
                (0, 0, 0, 2),
            ),
        )
