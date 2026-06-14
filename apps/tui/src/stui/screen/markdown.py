from __future__ import annotations

from dataclasses import dataclass

from pygments.styles import get_style_by_name
from rich.console import RenderableType
from rich.markdown import Heading, Markdown
from rich.syntax import PygmentsSyntaxTheme
from rich.theme import Theme

from stui.screen.theme import DEFAULT_TUI_THEME, TuiTheme

CODE_BLOCK_BACKGROUND = "#2A2F37"
_NORD_STYLE = get_style_by_name("nord")


class StuiNordStyle(_NORD_STYLE):
    background_color = CODE_BLOCK_BACKGROUND


PYGMENTS_CODE_THEME = PygmentsSyntaxTheme(StuiNordStyle)


class StuiHeading(Heading):
    LEVEL_ALIGN = {
        "h1": "left",
        "h2": "left",
        "h3": "left",
        "h4": "left",
        "h5": "left",
        "h6": "left",
    }


class StuiMarkdown(Markdown):
    elements = {
        **Markdown.elements,
        "heading_open": StuiHeading,
    }


@dataclass(frozen=True)
class MarkdownView:
    text: str
    theme: TuiTheme = DEFAULT_TUI_THEME

    def render(self) -> RenderableType:
        return ThemedMarkdown(
            markdown=StuiMarkdown(
                self.text,
                # Pygments theme for fenced code blocks.
                code_theme=PYGMENTS_CODE_THEME,
                # Base style for regular Markdown text.
                style=self.theme.color_text_primary,
            ),
            rich_theme=self._rich_markdown_theme(),
        )

    def _rich_markdown_theme(self) -> Theme:
        return Theme(
            {
                "markdown.h1": f"{self.theme.color_text_accent_secondary} bold",
                "markdown.h2": f"{self.theme.color_text_primary} bold",
                "markdown.h3": f"{self.theme.color_text_primary} bold",
                "markdown.code": (
                    f"{self.theme.color_text_inline_code} "
                    f"on {self.theme.color_background}"
                ),
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
