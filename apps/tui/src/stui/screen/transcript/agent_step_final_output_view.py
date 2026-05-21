from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType

from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView
from stui.screen.transcript.view_helpers import (
    render_message_content,
    wrap_agent_renderable,
)
from stui.viewmodel.console_screen_state import AgentStepFinalOutputItem


@dataclass(frozen=True)
class AgentStepFinalOutputView(TranscriptView):
    item: AgentStepFinalOutputItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        content = render_message_content(
            output=self.item.text,
            format=self.item.format,
            theme=theme,
        )
        return wrap_agent_renderable(content, theme=theme)
