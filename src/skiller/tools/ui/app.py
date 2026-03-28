from __future__ import annotations

from collections.abc import Callable

from skiller.tools.ui.runtime_adapter import CliRuntimeAdapter


def _load_prompt_toolkit_runner() -> Callable[..., str]:
    from skiller.tools.ui.tui_app import run_prompt_toolkit_ui

    return run_prompt_toolkit_ui


def run_ui(
    *,
    session_key: str | None = None,
    runtime_adapter: CliRuntimeAdapter | None = None,
    prompt_toolkit_runner: Callable[..., str] | None = None,
) -> str:
    runtime = runtime_adapter or CliRuntimeAdapter()
    runner = prompt_toolkit_runner or _load_prompt_toolkit_runner()
    return runner(
        session_key=session_key,
        runtime_adapter=runtime,
    )


def main() -> None:
    run_ui()
