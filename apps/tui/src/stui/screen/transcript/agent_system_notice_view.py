from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType

from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView
from stui.screen.transcript.view_helpers import prefixed_view, transcript_text
from stui.viewmodel.console_screen_state import AgentSystemNoticeItem


@dataclass(frozen=True)
class AgentSystemNoticeView(TranscriptView):
    item: AgentSystemNoticeItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        warning_style = theme.rich_style(theme.color_text_warning)
        return prefixed_view(
            prefix=transcript_text(
                theme.system_warning_icon,
                style=warning_style,
            ),
            content=transcript_text(
                self.item.text,
                style=warning_style,
            ),
            prefix_width=1,
        )
