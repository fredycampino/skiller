from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Static

from stui.di.strings import DEFAULT_TUI_STRINGS, TuiStrings
from stui.port.models_port import MODEL_PROVIDER_SOURCE_USER


@dataclass(frozen=True)
class AuthTableProviderRow:
    name: str
    adapter: str
    source: str


class AuthTableView(Vertical):
    def __init__(
        self,
        *,
        visible: bool = True,
        id: str | None = None,
        strings: TuiStrings = DEFAULT_TUI_STRINGS,
        **_: object,
    ) -> None:
        super().__init__(id=id)
        self.display = visible
        self._strings = strings
        self._providers_table = DataTable(
            id="auth-providers-table",
            show_header=False,
            show_row_labels=False,
            zebra_stripes=False,
            cursor_type="row",
            cursor_foreground_priority="css",
            cursor_background_priority="css",
        )
        self._providers: tuple[AuthTableProviderRow, ...] = ()
        self._provider_index = 0

    def compose(self) -> ComposeResult:
        yield self._providers_table
        yield Static(self._strings.auth_table_help, id="auth-help")

    def on_mount(self) -> None:
        self._render_table()

    def set_rows(self, rows: list[AuthTableProviderRow]) -> None:
        self._providers = tuple(rows)
        self._provider_index = self._clamp_index(self._provider_index)
        self._render_table()

    @property
    def selected_provider(self) -> AuthTableProviderRow | None:
        if not self._providers:
            return None
        return self._providers[self._provider_index]

    def move_selection(self, delta: int) -> bool:
        if not self._providers:
            return False
        next_index = self._clamp_index(self._provider_index + delta)
        if next_index == self._provider_index:
            return False
        self._provider_index = next_index
        if self.is_mounted:
            self._providers_table.move_cursor(row=self._provider_index)
        return True

    def action_select_cursor(self) -> None:
        self._providers_table.action_select_cursor()

    def render_providers_text(self) -> str:
        if not self._providers:
            return self._strings.auth_table_no_providers_message
        return "\n".join(
            format_provider_label(provider, self._strings)
            for provider in self._providers
        )

    def _render_table(self) -> None:
        if not self.is_mounted:
            return
        self._providers_table.styles.height = max(1, len(self._providers))
        self._providers_table.clear(columns=True)
        self._providers_table.add_column("")
        if not self._providers:
            self._providers_table.add_row(self._strings.auth_table_no_providers_message)
            return
        for provider in self._providers:
            self._providers_table.add_row(
                format_provider_label(provider, self._strings),
                key=provider.name,
            )
        self._providers_table.move_cursor(row=self._provider_index)

    def _clamp_index(self, index: int) -> int:
        if not self._providers:
            return 0
        return max(0, min(len(self._providers) - 1, index))


def format_provider_label(
    provider: AuthTableProviderRow,
    strings: TuiStrings = DEFAULT_TUI_STRINGS,
) -> str:
    marker = f" {strings.models_table_provider_configured_marker}"
    check = marker if provider.source == MODEL_PROVIDER_SOURCE_USER else ""
    return f"{provider.name} · {provider.adapter}{check}"
