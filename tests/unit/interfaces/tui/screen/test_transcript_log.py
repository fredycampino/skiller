from __future__ import annotations

import pytest
from rich.segment import Segment
from textual.geometry import Offset
from textual.selection import Selection
from textual.strip import Strip

from skiller.interfaces.tui.screen.transcript_log import TranscriptLog

pytestmark = pytest.mark.unit


def test_transcript_log_extracts_selection_from_rendered_lines() -> None:
    log = TranscriptLog()
    log.lines = [
        Strip([Segment("first line")], cell_length=len("first line")),
        Strip([Segment("second line")], cell_length=len("second line")),
    ]

    selected = log.get_selection(Selection.from_offsets(Offset(0, 0), Offset(6, 1)))

    assert selected is not None
    assert selected[0] == "first line\nsecond"
    assert selected[1] == "\n"
