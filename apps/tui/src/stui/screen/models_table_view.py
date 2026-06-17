from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Static

from stui.di.strings import DEFAULT_TUI_STRINGS, TuiStrings
from stui.port.models_port import MODEL_PROVIDER_SOURCE_NONE
from stui.screen.theme import DEFAULT_TUI_THEME, TuiTheme


@dataclass(frozen=True)
class ModelsTableModelRow:
    name: str
    active: bool = False


@dataclass(frozen=True)
class ModelsTableProviderRow:
    name: str
    source: str
    models: tuple[ModelsTableModelRow, ...]


class ModelsTableView(Vertical):
    def __init__(
        self,
        *,
        visible: bool = True,
        id: str | None = None,
        strings: TuiStrings = DEFAULT_TUI_STRINGS,
        theme: TuiTheme = DEFAULT_TUI_THEME,
        **_: object,
    ) -> None:
        super().__init__(id=id)
        self.display = visible
        self._strings = strings
        self._theme = theme
        self._providers_table = _build_table("models-providers-table", show_header=False)
        self._models_table = _build_table("models-models-table", show_header=False)
        self._providers: tuple[ModelsTableProviderRow, ...] = ()
        self._provider_index = 0
        self._model_index = 0
        self._model_index_by_provider: dict[str, int] = {}
        self._models_focused = False

    def compose(self) -> ComposeResult:
        yield Static("", id="models-status")
        yield Horizontal(
            self._providers_table,
            Vertical(
                self._models_table,
                id="models-column",
            ),
            id="models-tables-row",
        )
        yield Static(self._strings.models_table_help, id="models-help")

    def on_mount(self) -> None:
        self._render_tables()

    def set_rows(self, rows: list[ModelsTableProviderRow]) -> None:
        providers = ordered_providers(rows)
        if providers != self._providers:
            self._model_index_by_provider = {}
        self._providers = providers
        self._provider_index = self._initial_provider_index()
        self._model_index = self._stored_model_index(self.selected_provider)
        if not self._selected_provider_is_available():
            self._models_focused = False
        self._render_tables()

    @property
    def selected_provider(self) -> ModelsTableProviderRow | None:
        if not self._providers:
            return None
        if self._provider_index < 0 or self._provider_index >= len(self._providers):
            return None
        return self._providers[self._provider_index]

    @property
    def selected_model(self) -> ModelsTableModelRow | None:
        provider = self.selected_provider
        if provider is None or not provider_is_configured(provider):
            return None
        models = self._selected_models()
        if not models:
            return None
        if self._model_index < 0 or self._model_index >= len(models):
            return None
        model = models[self._model_index]
        if not self._models_focused and not model.active:
            return None
        return model

    @property
    def models_focused(self) -> bool:
        return self._models_focused

    def focus_providers(self) -> bool:
        self._models_focused = False
        self._sync_cursor_styles()
        return True

    def focus_models(self) -> bool:
        if not self._selected_provider_is_available():
            return False
        self._models_focused = True
        self._sync_cursor_styles()
        return True

    def move_selection(self, delta: int) -> bool:
        if self._models_focused:
            return self.move_model_selection(delta)
        return self.move_provider_selection(delta)

    def move_provider_selection(self, delta: int) -> bool:
        if not self._providers:
            return False
        next_index = max(0, min(len(self._providers) - 1, self._provider_index + delta))
        if next_index == self._provider_index:
            return False
        self._store_model_index()
        self._provider_index = next_index
        self._model_index = self._stored_model_index(self.selected_provider)
        if self.is_mounted:
            self._render_models_table()
        self._sync_cursor_styles()
        return True

    def move_model_selection(self, delta: int) -> bool:
        if not self._models_focused:
            return False
        models = self._selected_models()
        if not models:
            return False
        next_index = max(0, min(len(models) - 1, self._model_index + delta))
        if next_index == self._model_index:
            return False
        self._model_index = next_index
        self._store_model_index()
        self._sync_cursor_styles()
        return True

    def action_select_cursor(self) -> None:
        if self._models_focused:
            self._models_table.action_select_cursor()
            return
        self._providers_table.action_select_cursor()

    def render_providers_text(self) -> str:
        if not self._providers:
            return self._strings.models_table_no_providers_message
        return "\n".join(
            format_provider_label(provider, self._strings)
            for provider in self._providers
        )

    def render_models_text(self) -> str:
        provider = self.selected_provider
        models = self._selected_models()
        if provider is None or not models:
            return self._strings.models_table_no_models_message
        lines = [format_model_label(model, self._strings) for model in models]
        return "\n".join(lines)

    def _selected_models(self) -> tuple[ModelsTableModelRow, ...]:
        provider = self.selected_provider
        if provider is None:
            return ()
        return ordered_models(provider)

    def _selected_provider_is_available(self) -> bool:
        provider = self.selected_provider
        return provider is not None and provider_is_configured(provider) and bool(provider.models)

    def _render_tables(self) -> None:
        if not self.is_mounted:
            return
        self._render_providers_table()
        self._render_models_table()
        self._sync_cursor_styles()

    def _render_providers_table(self) -> None:
        self._providers_table.clear(columns=True)
        self._providers_table.add_column("")
        if not self._providers:
            self._providers_table.add_row(
                self._strings.models_table_no_providers_message
            )
            return
        for provider in self._providers:
            self._providers_table.add_row(
                format_provider_label(provider, self._strings),
                key=provider.name,
            )

    def _render_models_table(self) -> None:
        self._models_table.clear(columns=True)
        self.query_one("#models-status", Static).update(self._models_status_content())
        self._models_table.add_column("")
        provider = self.selected_provider
        models = self._selected_models()
        if provider is None or not models:
            self._models_table.add_row(self._strings.models_table_no_models_message)
            return
        for model in models:
            self._models_table.add_row(
                format_model_label(model, self._strings),
                key=model.name,
            )

    def _sync_cursor_styles(self) -> None:
        if not self.is_mounted:
            return
        if self._providers:
            self._providers_table.move_cursor(row=self._provider_index)
        models = self._selected_models()
        if models:
            self._models_table.move_cursor(row=self._model_index)
        self._providers_table.cursor_type = "row"
        self._models_table.cursor_type = "row" if self._models_focused else "none"
        self._providers_table.set_class(
            not self._models_focused,
            "models-table-focused",
        )
        self._providers_table.set_class(
            self._models_focused,
            "models-table-unfocused",
        )
        self._models_table.set_class(
            self._models_focused,
            "models-table-focused",
        )
        self._models_table.set_class(
            not self._models_focused,
            "models-table-unfocused",
        )

    def _initial_provider_index(self) -> int:
        if not self._providers:
            return 0
        if not self._model_index_by_provider:
            for index, provider in enumerate(self._providers):
                if provider_has_active_model(provider):
                    return index
        if 0 <= self._provider_index < len(self._providers):
            return self._provider_index
        return 0

    def _stored_model_index(self, provider: ModelsTableProviderRow | None) -> int:
        models = ordered_models(provider) if provider is not None else ()
        if not models:
            return 0
        stored_index = self._model_index_by_provider.get(provider.name)
        if stored_index is not None:
            return _clamp(stored_index, len(models))
        for index, model in enumerate(models):
            if model.active:
                return index
        return 0

    def _store_model_index(self) -> None:
        provider = self.selected_provider
        if provider is None or not provider.models:
            return
        self._model_index_by_provider[provider.name] = _clamp(
            self._model_index,
            len(provider.models),
        )

    def render_status_content(self) -> str | Text:
        text = self._models_status_text()
        provider = self.selected_provider
        if provider is not None and not provider_is_configured(provider):
            return Text(text, style=self._theme.color_text_warning)
        return text

    def _models_status_content(self) -> str | Text:
        return self.render_status_content()

    def _models_status_text(self) -> str:
        provider = self.selected_provider
        if provider is None:
            return self._strings.models_table_no_provider_selected_message
        if not provider_is_configured(provider):
            return self._strings.models_table_auth_required_template.format(
                provider=provider.name,
            )
        if not provider.models:
            return self._strings.models_table_no_models_for_provider_template.format(
                provider=provider.name,
            )
        return self._strings.models_table_select_model_title


def _build_table(id: str, *, show_header: bool) -> DataTable[object]:
    table: DataTable[object] = DataTable(
        id=id,
        show_header=show_header,
        show_row_labels=False,
        zebra_stripes=False,
        cursor_type="row",
        cursor_foreground_priority="css",
        cursor_background_priority="css",
    )
    table.show_horizontal_scrollbar = False
    table.show_vertical_scrollbar = False
    return table


def provider_is_configured(provider: ModelsTableProviderRow) -> bool:
    return provider.source != MODEL_PROVIDER_SOURCE_NONE


def format_provider_label(
    provider: ModelsTableProviderRow,
    strings: TuiStrings = DEFAULT_TUI_STRINGS,
) -> str:
    marker = f" {strings.models_table_provider_configured_marker}"
    check = marker if provider_is_configured(provider) else ""
    return f"{provider.name}{check}"


def ordered_providers(
    providers: list[ModelsTableProviderRow],
) -> tuple[ModelsTableProviderRow, ...]:
    return tuple(sorted(providers, key=lambda provider: not provider_is_configured(provider)))


def provider_has_active_model(provider: ModelsTableProviderRow) -> bool:
    return any(model.active for model in provider.models)


def ordered_models(provider: ModelsTableProviderRow) -> tuple[ModelsTableModelRow, ...]:
    active_models = tuple(model for model in provider.models if model.active)
    inactive_models = tuple(model for model in provider.models if not model.active)
    return active_models + inactive_models


def format_model_label(
    model: ModelsTableModelRow,
    strings: TuiStrings = DEFAULT_TUI_STRINGS,
) -> str:
    prefix = f"{strings.models_table_active_model_marker} " if model.active else "  "
    return f"{prefix}{model.name}"


def _clamp(index: int, length: int) -> int:
    if length <= 0:
        return 0
    return max(0, min(length - 1, index))
