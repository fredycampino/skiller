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
from stui.viewmodel.console_screen_state import (
    AgentContextCompactedItem,
    OutputFormat,
)


@dataclass(frozen=True)
class AgentContextCompactedView(TranscriptView):
    item: AgentContextCompactedItem
    strings: TuiStrings = DEFAULT_TUI_STRINGS

    def render(self, *, theme: TuiTheme) -> RenderableType:
        style = theme.color_text_success
        content = render_message_content(
            output=self.strings.agent_context_compacted_notice_template.format(
                estimated_request_tokens=self.item.estimated_request_tokens,
                estimated_request_compacted_tokens=(
                    self.item.estimated_request_compacted_tokens
                ),
            ),
            format=OutputFormat.SIMPLE,
            theme=theme,
            style=style,
        )
        return prefixed_view(
            prefix=transcript_text(theme.agent_context_compaction_icon, style=style),
            content=content,
            prefix_width=1,
        )
