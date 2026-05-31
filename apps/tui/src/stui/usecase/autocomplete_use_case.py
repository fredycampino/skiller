from __future__ import annotations

from dataclasses import dataclass

from stui.di.strings import DEFAULT_TUI_STRINGS, TuiStrings
from stui.viewmodel.console_screen_state import (
    CompletionItem,
    CompletionState,
)


@dataclass(frozen=True)
class AutocompleteUseCase:
    strings: TuiStrings = DEFAULT_TUI_STRINGS

    def execute(
        self,
        *,
        text: str,
        cursor_position: int,
    ) -> CompletionState | None:
        safe_cursor_position = max(0, min(len(text), cursor_position))
        query = text[:safe_cursor_position]
        if not query.startswith("/"):
            return None
        if any(char.isspace() for char in query):
            return None

        completion_catalog = (
            CompletionItem(
                label="run",
                description=self.strings.autocomplete_run_description,
                insert_text="/run",
                kind="command",
            ),
            CompletionItem(
                label="runs",
                description=self.strings.autocomplete_runs_description,
                insert_text="/runs",
                kind="command",
            ),
            CompletionItem(
                label="quit",
                description=self.strings.autocomplete_quit_description,
                insert_text="/quit",
                kind="command",
            ),
            CompletionItem(
                label="exit",
                description=self.strings.autocomplete_exit_description,
                insert_text="/exit",
                kind="command",
            ),
            CompletionItem(
                label="dev",
                description=self.strings.autocomplete_dev_description,
                insert_text="/dev",
                kind="command",
            ),
        )
        items = tuple(
            item
            for item in completion_catalog
            if item.insert_text.startswith(query) and item.insert_text != query
        )
        if not items:
            return None

        return CompletionState(
            visible=True,
            query=query,
            items=items,
            selected_index=0,
            replace_from=0,
            replace_to=safe_cursor_position,
        )
