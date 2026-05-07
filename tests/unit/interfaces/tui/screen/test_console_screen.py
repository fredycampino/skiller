from __future__ import annotations

import pytest

from skiller.interfaces.tui.port.runs_port import RunsPortItem
from skiller.interfaces.tui.screen.console_screen import _format_run_status

pytestmark = pytest.mark.unit


def test_format_run_status_adds_wait_type_suffix_when_present() -> None:
    assert _format_run_status(_run_item(status="WAITING", wait_type="input")) == "waiting-i"
    assert _format_run_status(_run_item(status="WAITING", wait_type="webhook")) == "waiting-w"
    assert _format_run_status(_run_item(status="WAITING", wait_type="channel")) == "waiting-c"


def test_format_run_status_leaves_plain_status_when_wait_type_is_missing() -> None:
    assert _format_run_status(_run_item(status="FAILED", wait_type=None)) == "failed"


def _run_item(*, status: str, wait_type: str | None) -> RunsPortItem:
    return RunsPortItem(
        id="run-1",
        skill_source="internal",
        skill_ref="chat",
        status=status,
        current="ask_user",
        created_at="2026-05-04 00:00:00",
        updated_at="2026-05-04 00:00:01",
        wait_type=wait_type,
    )
