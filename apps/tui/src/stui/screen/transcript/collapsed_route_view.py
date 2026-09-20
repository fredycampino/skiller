from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.text import Text

from stui.screen.theme import TuiTheme
from stui.screen.transcript.item_view import TranscriptItemView
from stui.viewmodel.console_screen_state import RunOutputItem, RunStepItem


@dataclass(frozen=True)
class CollapsedRouteView(TranscriptItemView):
    step: RunStepItem
    output: RunOutputItem
    target: str

    def render(self, *, theme: TuiTheme) -> RenderableType:
        _ = self.output
        return Text(
            f"   [{self.step.step_type}] {self.step.step_id} \u2192 {self.target}",
            style=theme.color_text_muted,
        )
