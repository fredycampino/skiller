from __future__ import annotations

import pytest

from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus

pytestmark = pytest.mark.unit


def test_activate_run_preserves_current_mode() -> None:
    context = RunEventContext(
        run_id="",
        skill_name="",
        mode=RunMode.CHAT,
        status=RunStatus.RUNNING,
    )

    context.activate_run(
        "run-1234",
        skill_name="ant",
        status=RunStatus.WAITING_INPUT,
    )

    assert context.run_id == "run-1234"
    assert context.skill_name == "ant"
    assert context.mode == RunMode.CHAT
    assert context.status == RunStatus.WAITING_INPUT
