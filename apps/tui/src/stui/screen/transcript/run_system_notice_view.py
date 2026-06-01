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
    OutputFormat,
    RunSnapshotStatus,
    RunSyncSnapshotItem,
)


@dataclass(frozen=True)
class RunSystemNoticeView(TranscriptView):
    item: RunSyncSnapshotItem
    strings: TuiStrings = DEFAULT_TUI_STRINGS

    def render(self, *, theme: TuiTheme) -> RenderableType:
        style = self._style(theme=theme)
        content = render_message_content(
            output=self._message(),
            format=OutputFormat.SIMPLE,
            theme=theme,
            style=style,
        )
        return prefixed_view(
            prefix=transcript_text(
                self._icon(theme=theme),
                style=style,
            ),
            content=content,
            prefix_width=1,
        )

    def _icon(self, *, theme: TuiTheme) -> str:
        if self.item.status == RunSnapshotStatus.UPDATED:
            return theme.status_icon_success
        return theme.system_warning_icon

    def _style(self, *, theme: TuiTheme) -> str:
        if self.item.status == RunSnapshotStatus.UPDATED:
            return theme.color_text_success
        return theme.color_text_warning

    def _message(self) -> str:
        if self.item.status == RunSnapshotStatus.UPDATED:
            return self.strings.run_snapshot_updated_notice_template.format(
                source=self.item.source,
                ref=self.item.ref,
            )
        return self.strings.run_snapshot_failed_notice_template.format(
            source=self.item.source,
            ref=self.item.ref,
            error=self.item.error,
        )
