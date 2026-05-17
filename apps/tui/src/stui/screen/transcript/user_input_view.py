from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.panel import Panel

from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView
from stui.screen.transcript.view_helpers import prefixed_view, transcript_text
from stui.viewmodel.console_screen_state import UserInputItem


@dataclass(frozen=True)
class UserInputView(TranscriptView):
    item: UserInputItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        return Panel(
            prefixed_view(
                prefix=transcript_text(
                    theme.user_icon,
                    style=theme.color_text_accent,
                ),
                content=transcript_text(
                    self.item.text,
                    style=theme.color_text_accent,
                ),
                prefix_width=1,
            ),
            border_style=theme.color_prompt_border,
            expand=True,
            padding=(0, 0),
        )
