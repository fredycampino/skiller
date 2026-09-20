from __future__ import annotations

from dataclasses import dataclass

from rich.console import Group, RenderableType
from rich.text import Text

from stui.screen.theme import TuiTheme
from stui.screen.transcript.item_view import TranscriptItemView
from stui.viewmodel.console_screen_state import RunAckItem


@dataclass(frozen=True)
class RunAckView(TranscriptItemView):
    item: RunAckItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        _ = theme
        return Group(
            Text(f"\u21b3 run({self.item.skill})"),
            Text(f"   created {self.item.run_id}"),
        )
