from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType

from stui.di.strings import DEFAULT_TUI_STRINGS, TuiStrings
from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView
from stui.screen.transcript.view_helpers import (
    prefixed_view,
    render_message_content,
    transcript_text,
)
from stui.viewmodel.console_screen_state import OutputFormat, RunModelUpdatedItem


@dataclass(frozen=True)
class RunModelUpdatedView(TranscriptView):
    item: RunModelUpdatedItem
    strings: TuiStrings = DEFAULT_TUI_STRINGS

    def render(self, *, theme: TuiTheme) -> RenderableType:
        style = theme.color_text_success
        content = render_message_content(
            output=self.strings.run_model_updated_notice_template.format(
                provider=self.item.provider,
                model=self.item.model,
            ),
            format=OutputFormat.SIMPLE,
            theme=theme,
            style=style,
        )
        return prefixed_view(
            prefix=transcript_text(theme.status_icon_success, style=style),
            content=content,
            prefix_width=1,
        )
