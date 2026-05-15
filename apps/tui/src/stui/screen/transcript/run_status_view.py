from __future__ import annotations

from dataclasses import dataclass

from rich.console import Group, RenderableType
from rich.padding import Padding
from rich.text import Text

from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView
from stui.viewmodel.console_screen_state import RunStatusItem


@dataclass(frozen=True)
class RunStatusView(TranscriptView):
    item: RunStatusItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        if self.item.status == "error":
            return self._render_error(theme=theme)
        return Text(f"  {self.item.status}")

    def _render_error(self, *, theme: TuiTheme) -> RenderableType:
        error_style = theme.rich_style(theme.color_text_error)
        if self.item.message:
            return Group(
                Text("  error:", style=error_style),
                Padding(Text(self.item.message, style=error_style), (0, 0, 0, 3)),
            )
        return Text("  error:", style=error_style)
