from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest
from rich.console import RenderableType
from rich.segment import Segment
from rich.text import Text
from textual.app import App, ComposeResult
from textual.geometry import Offset
from textual.selection import Selection
from textual.strip import Strip

from stui.screen.theme import DEFAULT_TUI_THEME, TuiTheme
from stui.screen.transcript import RenderTranscript
from stui.screen.transcript_view import TranscriptView
from stui.viewmodel.console_screen_state import (
    TranscriptItem,
    TranscriptMode,
    TranscriptState,
    UserInputItem,
)

pytestmark = pytest.mark.unit


@dataclass
class RecordingTranscriptRenderer:
    calls: list[tuple[TranscriptMode, tuple[TranscriptItem, ...]]] = field(
        default_factory=list
    )

    def render(
        self,
        *,
        items: list[TranscriptItem],
        mode: TranscriptMode,
        theme: TuiTheme,
        prompt_placeholder: str | None,
    ) -> list[RenderableType]:
        _ = theme, prompt_placeholder
        self.calls.append((mode, tuple(items)))
        return [Text(item.text) for item in items if isinstance(item, UserInputItem)]


class TranscriptViewApp(App[None]):
    def __init__(self, *, renderer: RecordingTranscriptRenderer) -> None:
        super().__init__()
        self.renderer = renderer

    def compose(self) -> ComposeResult:
        yield TranscriptView(
            renderer=self.renderer,
            theme=DEFAULT_TUI_THEME,
            id="transcript",
        )


def test_transcript_view_skips_unchanged_state() -> None:
    async def run() -> None:
        renderer = RecordingTranscriptRenderer()
        app = TranscriptViewApp(renderer=renderer)
        state = TranscriptState(items=[UserInputItem(text="message")])

        async with app.run_test(size=(80, 24)):
            transcript = app.query_one("#transcript", TranscriptView)
            transcript.set_state(state)
            transcript.set_state(
                TranscriptState(mode=state.mode, items=list(state.items))
            )

            assert renderer.calls == [(state.mode, tuple(state.items))]

    asyncio.run(run())


def test_transcript_view_extracts_selection_from_rendered_lines() -> None:
    log = TranscriptView(
        renderer=RenderTranscript(),
        theme=DEFAULT_TUI_THEME,
    )
    log.lines = [
        Strip([Segment("first line")], cell_length=len("first line")),
        Strip([Segment("second line")], cell_length=len("second line")),
    ]

    selected = log.get_selection(Selection.from_offsets(Offset(0, 0), Offset(6, 1)))

    assert selected is not None
    assert selected[0] == "first line\nsecond"
    assert selected[1] == "\n"
