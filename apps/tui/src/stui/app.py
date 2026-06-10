from __future__ import annotations

from collections.abc import Callable

from stui.di.strings import DEFAULT_TUI_STRINGS, TuiStrings
from stui.screen.theme import DEFAULT_TUI_THEME, TuiTheme


def _load_textual_runner() -> Callable[..., str]:
    try:
        from stui.screen.console_screen import run_console_screen
    except ImportError as exc:
        raise RuntimeError("textual is not installed") from exc
    return run_console_screen


def run_tui(
    *,
    session_key: str | None = None,
    textual_runner: Callable[..., str] | None = None,
    theme: TuiTheme = DEFAULT_TUI_THEME,
    strings: TuiStrings = DEFAULT_TUI_STRINGS,
) -> str:
    runner = textual_runner or _load_textual_runner()
    return runner(
        session_key=session_key or "main",
        theme=theme,
        strings=strings,
    )


def main() -> None:
    run_tui()
