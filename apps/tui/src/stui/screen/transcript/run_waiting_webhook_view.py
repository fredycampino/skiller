from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.padding import Padding
from rich.text import Text

from stui.di.strings import DEFAULT_TUI_STRINGS, TuiStrings
from stui.screen.theme import TuiTheme
from stui.screen.transcript.base import TranscriptView
from stui.screen.transcript.view_helpers import wrap_message_renderable
from stui.viewmodel.console_screen_state import RunWaitingWebhookItem


@dataclass(frozen=True)
class RunWaitingWebhookView(TranscriptView):
    item: RunWaitingWebhookItem
    strings: TuiStrings = DEFAULT_TUI_STRINGS

    def render(self, *, theme: TuiTheme) -> RenderableType:
        style = theme.color_text_muted if self.item.muted else theme.color_text_warning
        content = wrap_message_renderable(
            Text(self._message(), style=style),
            theme=theme,
            icon=self.item.icon,
            icon_style=style,
        )
        return Padding(content, (1, 0, 0, 0))

    def _message(self) -> str:
        if self.item.webhook and self.item.key:
            return f"{self.strings.waiting_webhook_message}:\n{self.item.webhook}/{self.item.key}"
        if self.item.webhook:
            return f"{self.strings.waiting_webhook_message}: {self.item.webhook}."
        return f"{self.strings.waiting_webhook_message}."
