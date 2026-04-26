from __future__ import annotations

from textual.selection import Selection
from textual.widgets import RichLog


class TranscriptLog(RichLog):
    def get_selection(self, selection: Selection) -> tuple[str, str] | None:
        if not self.lines:
            return None

        text = "\n".join(strip.text for strip in self.lines)
        return selection.extract(text), "\n"
