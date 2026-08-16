from __future__ import annotations

from dataclasses import dataclass

from stui.di.strings import DEFAULT_TUI_STRINGS, TuiStrings
from stui.viewmodel.console_screen_state import (
    CompletionItem,
    CompletionState,
)

_COMMAND_KIND = "command"


@dataclass(frozen=True)
class AutocompleteQuery:
    text: str
    cursor_position: int

    @property
    def has_arguments(self) -> bool:
        return " " in self.text


@dataclass(frozen=True)
class AutocompleteUseCase:
    strings: TuiStrings = DEFAULT_TUI_STRINGS

    def execute(
        self,
        *,
        text: str,
        cursor_position: int,
    ) -> CompletionState | None:
        query = _autocomplete_query(text=text, cursor_position=cursor_position)
        if query is None:
            return None

        if query.has_arguments:
            return None

        return self._complete_command(query=query)

    def _complete_command(self, *, query: AutocompleteQuery) -> CompletionState | None:
        items = _matching_command_items(
            catalog=self._command_catalog(),
            query_text=query.text,
        )
        return _completion_state(
            query_text=query.text,
            items=items,
            replace_from=0,
            replace_to=query.cursor_position,
        )

    def _command_catalog(self) -> tuple[CompletionItem, ...]:
        return (
            CompletionItem(
                label="run",
                description=self.strings.autocomplete_run_description,
                insert_text="/run",
                kind=_COMMAND_KIND,
            ),
            CompletionItem(
                label="runs",
                description=self.strings.autocomplete_runs_description,
                insert_text="/runs",
                kind=_COMMAND_KIND,
            ),
            CompletionItem(
                label="auth",
                description=self.strings.autocomplete_auth_description,
                insert_text="/auth",
                kind=_COMMAND_KIND,
            ),
            CompletionItem(
                label="models",
                description=self.strings.autocomplete_models_description,
                insert_text="/models",
                kind=_COMMAND_KIND,
            ),
            CompletionItem(
                label="quit",
                description=self.strings.autocomplete_quit_description,
                insert_text="/quit",
                kind=_COMMAND_KIND,
            ),
            CompletionItem(
                label="exit",
                description=self.strings.autocomplete_exit_description,
                insert_text="/exit",
                kind=_COMMAND_KIND,
            ),
            CompletionItem(
                label="dev",
                description=self.strings.autocomplete_dev_description,
                insert_text="/dev",
                kind=_COMMAND_KIND,
            ),
        )


def _autocomplete_query(*, text: str, cursor_position: int) -> AutocompleteQuery | None:
    safe_cursor_position = max(0, min(len(text), cursor_position))
    query_text = text[:safe_cursor_position]
    if not query_text.startswith("/"):
        return None
    return AutocompleteQuery(text=query_text, cursor_position=safe_cursor_position)


def _matching_command_items(
    *,
    catalog: tuple[CompletionItem, ...],
    query_text: str,
) -> tuple[CompletionItem, ...]:
    return tuple(
        item
        for item in catalog
        if _command_match_text(item).startswith(query_text)
        and _command_match_text(item) != query_text
    )


def _command_match_text(item: CompletionItem) -> str:
    return item.insert_text.rstrip()


def _completion_state(
    *,
    query_text: str,
    items: tuple[CompletionItem, ...],
    replace_from: int,
    replace_to: int,
) -> CompletionState | None:
    if not items:
        return None
    return CompletionState(
        visible=True,
        query=query_text,
        items=items,
        selected_index=0,
        replace_from=replace_from,
        replace_to=replace_to,
    )
