from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.text import Text

from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView
from stui.viewmodel.console_screen_state import RunOutputItem, RunStepItem


@dataclass(frozen=True)
class CollapsedRouteView(TranscriptView):
    step: RunStepItem
    output: RunOutputItem
    target: str

    def render(self, *, theme: TuiTheme) -> RenderableType:
        _ = self.output
        return Text(
            f"   [{self.step.step_type}] {self.step.step_id} \u2192 {self.target}",
            style=theme.rich_style(theme.color_text_muted),
        )
