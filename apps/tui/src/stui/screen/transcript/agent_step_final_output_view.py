from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType

from stui.screen.theme import TuiTheme
from stui.screen.transcript.item_view import TranscriptItemView
from stui.screen.transcript.view_helpers import (
    render_message_content,
    with_generation_speed,
    wrap_agent_renderable,
)
from stui.viewmodel.console_screen_state import AgentStepFinalOutputItem


@dataclass(frozen=True)
class AgentStepFinalOutputView(TranscriptItemView):
    item: AgentStepFinalOutputItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        content = render_message_content(
            output=self.item.final,
            format=self.item.format,
            theme=theme,
        )
        return with_generation_speed(
            wrap_agent_renderable(content, theme=theme),
            output_tokens_per_second=self.item.output_tokens_per_second,
            theme=theme,
        )
