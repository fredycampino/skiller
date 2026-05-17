from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.text import Text

from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView
from stui.screen.transcript.view_helpers import agent_step_id_style, agent_step_tag_style
from stui.viewmodel.console_screen_state import RunStepItem, TranscriptMode

_WAIT_STEP_TYPES = {
    "wait_input",
    "wait_webhook",
    "wait_channel",
}


@dataclass(frozen=True)
class RunStepView(TranscriptView):
    item: RunStepItem
    mode: TranscriptMode

    def render(self, *, theme: TuiTheme) -> RenderableType:
        normalized_step_type = self.item.step_type.strip().lower()
        if normalized_step_type in _WAIT_STEP_TYPES:
            return Text(
                "   ...",
                style=theme.color_text_muted,
            )
        if normalized_step_type == "agent":
            return self._render_agent_step(theme=theme)
        return Text(f"   [{self.item.step_type}] {self.item.step_id}")

    def _render_agent_step(self, *, theme: TuiTheme) -> Text:
        tag_style = agent_step_tag_style(theme=theme, mode=self.mode)
        id_style = agent_step_id_style(theme=theme, mode=self.mode)
        renderable = Text("[")
        renderable.stylize(tag_style, 0, 1)
        renderable.append(
            self.item.step_type,
            style=tag_style,
        )
        renderable.append("] ")
        renderable.stylize(tag_style, len(renderable.plain) - 2, len(renderable.plain))
        renderable.append(
            self.item.step_id,
            style=id_style,
        )
        return renderable
