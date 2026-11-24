from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text

from stui.screen.theme import TuiTheme
from stui.screen.transcript.item_view import TranscriptItemView
from stui.screen.transcript.view_helpers import (
    render_agent_assistant_content,
    with_generation_speed,
    wrap_agent_renderable,
)
from stui.viewmodel.console_screen_state import AgentAssistantMessageItem


@dataclass(frozen=True)
class AgentAssistantMessageView(TranscriptItemView):
    item: AgentAssistantMessageItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        if self.item.is_empty:
            row = Table.grid(expand=True, padding=0)
            row.add_column(ratio=1)
            row.add_column(justify="right")
            speed = self.item.output_tokens_per_second
            row.add_row(
                Text(f"{theme.agent_message_icon} ▪▪▪", style=theme.color_text_muted),
                Text(f"{speed:.0f} t/s" if speed is not None else "", style=theme.color_text_muted),
            )
            return row
        content = wrap_agent_renderable(
            render_agent_assistant_content(
                item=self.item,
                theme=theme,
            ),
            theme=theme,
        )
        return with_generation_speed(
            content,
            output_tokens_per_second=self.item.output_tokens_per_second,
            theme=theme,
        )
