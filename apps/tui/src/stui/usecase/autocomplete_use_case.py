from __future__ import annotations

from dataclasses import dataclass

from stui.viewmodel.console_screen_state import (
    CompletionItem,
    CompletionState,
)

_COMPLETION_CATALOG: tuple[CompletionItem, ...] = (
    CompletionItem(
        label="run",
        description="Run a skill",
        insert_text="/run",
        kind="command",
    ),
    CompletionItem(
        label="chat",
        description="Run a skill in chat mode",
        insert_text="/chat",
        kind="command",
    ),
    CompletionItem(
        label="runs",
        description="Show runs",
        insert_text="/runs",
        kind="command",
    ),
    CompletionItem(
        label="chats",
        description="Show waiting input chats",
        insert_text="/chats",
        kind="command",
    ),
    CompletionItem(
        label="quit",
        description="Exit the TUI",
        insert_text="/quit",
        kind="command",
    ),
    CompletionItem(
        label="dev",
        description="Show local debug state",
        insert_text="/dev",
        kind="command",
    ),
)


@dataclass(frozen=True)
class AutocompleteUseCase:
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

        items = tuple(
            item
            for item in _COMPLETION_CATALOG
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
