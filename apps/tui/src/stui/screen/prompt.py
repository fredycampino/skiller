from __future__ import annotations

from dataclasses import dataclass

from textual import events
from textual.containers import Horizontal
from textual.widgets import Static, TextArea

from stui.screen.theme import DEFAULT_TUI_THEME, TuiTheme
from stui.viewmodel.console_screen_state import PromptState

MAX_INLINE_PASTE_CHARS = 160


class PromptTextArea(TextArea):
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        super().__init__(*args, **kwargs)
        self._multiline_paste_count = 0
        self._multiline_paste_payloads: dict[str, str] = {}

    async def _on_paste(self, event: events.Paste) -> None:
        normalized_text = event.text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
        is_short_single_line = (
            len(normalized_text.splitlines()) <= 1
            and len(normalized_text) <= MAX_INLINE_PASTE_CHARS
        )
        if is_short_single_line:
            event.text = normalized_text
            await super()._on_paste(event)
            event.prevent_default()
            event.stop()
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


class PromptView(Horizontal):
    def __init__(
        self,
        *,
        theme: TuiTheme = DEFAULT_TUI_THEME,
        id: str = "prompt-row",
    ) -> None:
        self._ignore_next_change = False
        super().__init__(
            Static(theme.cursor, id="prompt-prefix"),
            PromptTextArea(
                "",
                id="prompt",
                placeholder=theme.prompt_placeholder,
                soft_wrap=True,
                compact=True,
                show_line_numbers=False,
                highlight_cursor_line=False,
            ),
            id=id,
        )

    def controller(self) -> "PromptController":
        return PromptController(self.query_one("#prompt", TextArea))

    def focus_prompt(self) -> None:
        self.controller().focus()

    def set_prompt_state(self, *, state: PromptState) -> None:
        prompt = self.controller()
        if (
            prompt.text() == state.text
            and prompt.cursor_position() == state.cursor_position
        ):
            return

        self._ignore_next_change = True
        prompt.set_text(
            state.text,
            cursor_position=state.cursor_position,
        )

    def consume_programmatic_change(self) -> bool:
        if not self._ignore_next_change:
            return False
        self._ignore_next_change = False
        return True


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
    text = text.rstrip("\n")
    if len(text.splitlines()) <= 1 and len(text) <= MAX_INLINE_PASTE_CHARS:
        return text

    lines = text.splitlines()
    if not lines:
        return ""
    extra_lines = max(0, len(lines) - 1)
    line_label = "line" if extra_lines == 1 else "lines"
    return f"[paste #{paste_count} +{extra_lines} {line_label}]"
