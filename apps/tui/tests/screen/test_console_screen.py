from __future__ import annotations

import pytest

from stui.port.runs_port import RunsPortItem
from stui.screen.console_screen import (
    _build_footer_left_text,
    _build_footer_right_text,
    _format_agent_tokens,
    _format_run_updated_at,
    _resolve_run_row_status,
)
from stui.screen.runs_table_view import RunRowStatus
from stui.viewmodel.console_screen_state import (
    AgentUsageState,
    ConsoleScreenState,
)

pytestmark = pytest.mark.unit


def test_resolve_run_row_status_maps_wait_variants() -> None:
    assert (
        _resolve_run_row_status(_run_item(status="WAITING", wait_type="input"))
        == RunRowStatus.WAITING_INPUT
    )
    assert (
        _resolve_run_row_status(_run_item(status="WAITING", wait_type="webhook"))
        == RunRowStatus.WAITING_WEBHOOK
    )
    assert (
        _resolve_run_row_status(_run_item(status="WAITING", wait_type="channel"))
        == RunRowStatus.WAITING_CHANNEL
    )


def test_resolve_run_row_status_maps_terminal_and_running_statuses() -> None:
    assert (
        _resolve_run_row_status(_run_item(status="FAILED", wait_type=None))
        == RunRowStatus.FAILED
    )
    assert (
        _resolve_run_row_status(_run_item(status="SUCCEEDED", wait_type=None))
        == RunRowStatus.SUCCESS
    )
    assert (
        _resolve_run_row_status(_run_item(status="RUNNING", wait_type=None))
        == RunRowStatus.RUNNING
    )


def test_format_run_updated_at_uses_short_month_day_and_time() -> None:
    assert _format_run_updated_at("2026-05-04 00:00:01") == "05-04 00:00"
    assert _format_run_updated_at("2026-05-04T17:29:08Z") == "05-04 17:29"
    assert _format_run_updated_at("") == "-"
    assert _format_run_updated_at("invalid") == "-"


def test_format_agent_tokens_uses_compact_k_units() -> None:
    assert _format_agent_tokens(999) == "999"
    assert _format_agent_tokens(3155) == "3.2k"


def test_build_footer_left_text_shows_usage_when_available() -> None:
    state = ConsoleScreenState(
        agent_usage=AgentUsageState(
            model="MiniMax-M2.5",
            total_tokens=3155,
        )
    )

    assert _build_footer_left_text(state=state) == "MiniMax-M2.5\n3.2k"


def test_build_footer_left_text_falls_back_to_commands_hint() -> None:
    assert _build_footer_left_text(state=ConsoleScreenState()) == "/ for commands"


def test_build_footer_right_text_shows_run_id_and_compact_run_name() -> None:
    state = ConsoleScreenState(
        session_key="run-1234",
        run_name="apps/tui/tests/flows/notify/notify.yaml",
    )

    assert (
        _build_footer_right_text(state=state, empty_icon="-")
        == "run-1234\n/notify.yaml"
    )


def test_build_footer_right_text_shows_empty_icon_without_run() -> None:
    assert _build_footer_right_text(state=ConsoleScreenState(), empty_icon="-") == "-"


def _run_item(*, status: str, wait_type: str | None) -> RunsPortItem:
    return RunsPortItem(
        id="run-1",
        source="internal",
        ref="chat",
        status=status,
        current="ask_user",
        created_at="2026-05-04 00:00:00",
        updated_at="2026-05-04 00:00:01",
        wait_type=wait_type,
    )
