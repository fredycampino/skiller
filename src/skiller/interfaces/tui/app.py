from __future__ import annotations

from collections.abc import Callable

from skiller.interfaces.tui.screen.theme import DEFAULT_TUI_THEME, TuiTheme


def _load_textual_runner() -> Callable[..., str]:
    try:
        from skiller.interfaces.tui.screen.console_screen import run_console_screen
    except ImportError as exc:
        raise RuntimeError("textual is not installed") from exc
    return run_console_screen


def run_tui(
    *,
    session_key: str | None = None,
    textual_runner: Callable[..., str] | None = None,
    theme: TuiTheme = DEFAULT_TUI_THEME,
) -> str:
    runner = textual_runner or _load_textual_runner()
    return runner(
        session_key=session_key or "main",
        theme=theme,
    )


def main() -> None:
    run_tui()
