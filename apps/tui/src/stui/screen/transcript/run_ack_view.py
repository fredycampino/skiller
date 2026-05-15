from __future__ import annotations

from dataclasses import dataclass

from rich.console import Group, RenderableType
from rich.text import Text

from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView
from stui.viewmodel.console_screen_state import RunAckItem


@dataclass(frozen=True)
class RunAckView(TranscriptView):
    item: RunAckItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        _ = theme
        return Group(
            Text(f"\u21b3 run({self.item.skill})"),
            Text(f"   created {self.item.run_id}"),
        )
