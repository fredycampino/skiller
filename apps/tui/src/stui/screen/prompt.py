from __future__ import annotations

from dataclasses import dataclass

from textual import events
from textual.widgets import TextArea


class PromptTextArea(TextArea):
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        super().__init__(*args, **kwargs)
        self._multiline_paste_count = 0
        self._multiline_paste_payloads: dict[str, str] = {}

    async def _on_paste(self, event: events.Paste) -> None:
        normalized_text = event.text.replace("\r\n", "\n").replace("\r", "\n")
        if "\n" not in normalized_text:
            await super()._on_paste(event)
            return

        self._multiline_paste_count += 1
        compacted_text = compact_pasted_prompt_text(
            normalized_text,
            paste_count=self._multiline_paste_count,
        )
        self._multiline_paste_payloads[compacted_text] = normalized_text

        if self.read_only:
            return
        if result := self._replace_via_keyboard(compacted_text, *self.selection):
            self.move_cursor(result.end_location)
            self.focus()
            self._sync_multiline_paste_payloads()
        event.prevent_default()
        event.stop()

    def decoded_text(self) -> str:
        self._sync_multiline_paste_payloads()
        resolved_text = self.text
        for token, payload in self._multiline_paste_payloads.items():
            if token in resolved_text:
                resolved_text = resolved_text.replace(token, payload)
        return resolved_text

    def sync_paste_memory(self) -> None:
        self._sync_multiline_paste_payloads()

    def _sync_multiline_paste_payloads(self) -> None:
        current_text = self.text
        if not current_text:
            self._multiline_paste_payloads.clear()
            return
        stale_tokens = [
            token
            for token in self._multiline_paste_payloads
            if token not in current_text
        ]
        for token in stale_tokens:
            self._multiline_paste_payloads.pop(token, None)


@dataclass(frozen=True)
class PromptController:
    widget: object

    def text(self) -> str:
        decoded_text = getattr(self.widget, "decoded_text", None)
        if callable(decoded_text):
            return str(decoded_text())
        return str(getattr(self.widget, "text"))

    def normalized_text(self) -> str:
        return self.text().strip()

    def cursor_position(self) -> int:
        return text_area_cursor_position(self.widget)

    def set_text(self, text: str, *, cursor_position: int | None = None) -> None:
        setattr(self.widget, "text", text)
        sync_paste_memory = getattr(self.widget, "sync_paste_memory", None)
        if callable(sync_paste_memory):
            sync_paste_memory()
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


def compact_pasted_prompt_text(text: str, *, paste_count: int) -> str:
    if "\n" not in text:
        return text

    lines = text.splitlines()
    if not lines:
        return ""
    extra_lines = max(0, len(lines) - 1)
    line_label = "line" if extra_lines == 1 else "lines"
    return f"[paste #{paste_count} +{extra_lines} {line_label}]"
