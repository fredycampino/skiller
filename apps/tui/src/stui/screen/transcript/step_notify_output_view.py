from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType

from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView
from stui.screen.transcript.view_helpers import (
    render_message_content,
    wrap_message_renderable,
)
from stui.viewmodel.console_screen_state import StepNotifyOutputItem


@dataclass(frozen=True)
class StepNotifyOutputView(TranscriptView):
    item: StepNotifyOutputItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        content_style = theme.color_text_secondary if self.item.muted else ""
        content = render_message_content(
            output=self.item.message,
            format=self.item.format,
            theme=theme,
            style=content_style,
        )
        return wrap_message_renderable(
            content,
            theme=theme,
            icon=self.item.icon,
            muted=self.item.muted,
        )
