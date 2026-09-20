from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.text import Text

from stui.screen.theme import TuiTheme
from stui.screen.transcript.item_view import TranscriptItemView
from stui.viewmodel.console_screen_state import AgentFinalAssistantMessageItem


@dataclass(frozen=True)
class AgentFinalAssistantMessageView(TranscriptItemView):
    item: AgentFinalAssistantMessageItem

    def render(self, *, theme: TuiTheme) -> RenderableType:
        _ = theme
        return Text("")
