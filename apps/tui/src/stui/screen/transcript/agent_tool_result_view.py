from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.padding import Padding

from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView
from stui.screen.transcript.view_helpers import transcript_text
from stui.viewmodel.console_screen_state import AgentToolResultItem


@dataclass(frozen=True)
class AgentToolResultView(TranscriptView):
    item: AgentToolResultItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        return Padding(
            transcript_text(
                self.item.preview,
                style=theme.rich_style(theme.color_text_muted),
            ),
            (0, 0, 0, 4),
        )
