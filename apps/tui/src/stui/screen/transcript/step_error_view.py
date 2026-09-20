from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType

from stui.screen.theme import TuiTheme
from stui.screen.transcript.item_view import TranscriptItemView
from stui.screen.transcript.view_helpers import (
    render_message_content,
    wrap_message_renderable,
)
from stui.viewmodel.console_screen_state import OutputFormat, StepErrorItem


@dataclass(frozen=True)
class StepErrorView(TranscriptItemView):
    item: StepErrorItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        error_style = theme.color_text_error
        content = render_message_content(
            output=self.item.message,
            format=OutputFormat.SIMPLE,
            theme=theme,
            style=error_style,
        )
        return wrap_message_renderable(
            content,
            theme=theme,
            icon="×",
            icon_style=error_style,
        )
