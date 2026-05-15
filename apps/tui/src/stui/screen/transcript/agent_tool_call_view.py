from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType

from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView
from stui.screen.transcript.view_helpers import prefixed_view, transcript_text
from stui.viewmodel.console_screen_state import AgentToolCallItem


@dataclass(frozen=True)
class AgentToolCallView(TranscriptView):
    item: AgentToolCallItem
    active: bool = False

    def render(self, *, theme: TuiTheme) -> RenderableType:
        tool_style = (
            theme.rich_style(theme.color_text_primary)
            if self.active
            else theme.rich_style(theme.color_text_muted)
        )
        return prefixed_view(
            prefix=transcript_text(
                theme.agent_tool_icon,
                style=tool_style,
            ),
            content=transcript_text(
                f"$ {self.item.command}",
                style=tool_style,
            ),
            prefix_width=1,
        )
