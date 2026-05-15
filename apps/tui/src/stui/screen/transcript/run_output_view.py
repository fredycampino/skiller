from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType

from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView
from stui.screen.transcript.view_helpers import render_run_output
from stui.viewmodel.console_screen_state import RunOutputItem


@dataclass(frozen=True)
class RunOutputView(TranscriptView):
    item: RunOutputItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        return render_run_output(
            theme=theme,
            step_type=self.item.step_type,
            output=self.item.output,
            format=self.item.format,
        )
