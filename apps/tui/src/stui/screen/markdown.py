from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.markdown import Markdown
from rich.theme import Theme

from stui.screen.theme import DEFAULT_TUI_THEME, TuiTheme

PYGMENTS_CODE_THEME = "nord"


@dataclass(frozen=True)
class MarkdownView:
    text: str
    theme: TuiTheme = DEFAULT_TUI_THEME

    def render(self) -> RenderableType:
        return ThemedMarkdown(
            markdown=Markdown(
                self.text,
                # Pygments theme for fenced code blocks.
                code_theme=PYGMENTS_CODE_THEME,
                # Base style for regular Markdown text.
                style=self.theme.color_ansi_default,
            ),
            rich_theme=self._rich_markdown_theme(),
        )

    def _rich_markdown_theme(self) -> Theme:
        return Theme(
            {
                "markdown.h2": f"{self.theme.color_text_primary} bold",
                "markdown.h3": f"{self.theme.color_text_primary} bold",
                "markdown.code": f"{self.theme.color_text_inline_code} on default",
                "markdown.table.header": f"{self.theme.color_text_primary} bold",
                "markdown.table.border": self.theme.color_text_muted,
            }
        )


@dataclass(frozen=True)
class ThemedMarkdown:
    markdown: Markdown
    rich_theme: Theme

    def __rich_console__(self, console, options):  # noqa: ANN001
        with console.use_theme(self.rich_theme):
            yield from console.render(self.markdown, options)
