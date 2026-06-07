from __future__ import annotations

import pytest

from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus

pytestmark = pytest.mark.unit


def test_activate_run_preserves_current_mode() -> None:
    context = RunEventContext(
        run_id="",
        run_name="",
        mode=RunMode.CHAT,
        status=RunStatus.RUNNING,
    )

    context.activate_run(
        "run-1234",
        run_name="ant",
        status=RunStatus.WAITING_INPUT,
    )

    assert context.run_id == "run-1234"
    assert context.run_name == "ant"
    assert context.mode == RunMode.CHAT
    assert context.status == RunStatus.WAITING_INPUT


def test_activate_run_clears_done_actions() -> None:
    context = RunEventContext(
        run_id="run-1",
        run_name="run",
        mode=RunMode.CHAT,
        status=RunStatus.RUNNING,
        actions_done={"action-1"},
    )

    context.activate_run(
        "run-2",
        run_name="next",
        status=RunStatus.RUNNING,
    )

    assert context.actions_done == set()
