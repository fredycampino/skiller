from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType

from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView
from stui.screen.transcript.view_helpers import (
    render_agent_assistant_content,
    wrap_agent_renderable,
)
from stui.viewmodel.console_screen_state import AgentAssistantMessageItem


@dataclass(frozen=True)
class AgentAssistantMessageView(TranscriptView):
    item: AgentAssistantMessageItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        return wrap_agent_renderable(
            render_agent_assistant_content(
                item=self.item,
                theme=theme,
            ),
            theme=theme,
        )
