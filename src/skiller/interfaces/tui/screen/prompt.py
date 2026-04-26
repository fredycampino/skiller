from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptController:
    widget: object

    def text(self) -> str:
        return str(getattr(self.widget, "text"))

    def normalized_text(self) -> str:
        return self.text().strip()

    def cursor_position(self) -> int:
        return text_area_cursor_position(self.widget)

    def set_text(self, text: str, *, cursor_position: int | None = None) -> None:
        setattr(self.widget, "text", text)
        if cursor_position is not None:
            setattr(self.widget, "cursor_location", text_offset_to_location(text, cursor_position))

    def clear(self) -> None:
        self.set_text("", cursor_position=0)

    def focus(self) -> None:
        focus = getattr(self.widget, "focus")
        focus()

    def set_disabled(self, disabled: bool) -> None:
        setattr(self.widget, "disabled", disabled)


def text_area_cursor_position(prompt: object) -> int:
    text = str(getattr(prompt, "text"))
    row, column = getattr(prompt, "cursor_location")
    lines = text.split("\n")
    safe_row = max(0, min(len(lines) - 1, int(row)))
    safe_column = max(0, min(len(lines[safe_row]), int(column)))
    return sum(len(line) + 1 for line in lines[:safe_row]) + safe_column


def text_offset_to_location(text: str, cursor_position: int) -> tuple[int, int]:
    safe_position = max(0, min(len(text), cursor_position))
    current_offset = 0
    lines = text.split("\n")
    for row, line in enumerate(lines):
        line_end = current_offset + len(line)
        if safe_position <= line_end:
            return row, safe_position - current_offset
        current_offset = line_end + 1
    return len(lines) - 1, len(lines[-1])
