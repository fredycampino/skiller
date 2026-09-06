from __future__ import annotations

import pytest

from stui.app import run_tui

pytestmark = pytest.mark.unit


def test_run_tui_forwards_initial_run_arguments() -> None:
    calls: list[dict[str, object]] = []

    def textual_runner(**kwargs: object) -> str:
        calls.append(kwargs)
        return "run-1"

    result = run_tui(
        initial_run_args=("@flows",),
        textual_runner=textual_runner,
    )

    assert result == "run-1"
    assert calls[0]["session_key"] == "main"
    assert calls[0]["initial_run_args"] == ("@flows",)
