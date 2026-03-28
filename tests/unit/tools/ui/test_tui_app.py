from __future__ import annotations

import pytest
from prompt_toolkit.buffer import Buffer, CompletionState
from prompt_toolkit.completion import Completion
from prompt_toolkit.document import Document

from skiller.tools.ui.actions import ActionResult
from skiller.tools.ui.commands import InputCommand, StatusCommand, WatchCommand
from skiller.tools.ui.session import UiRun, UiSession
from skiller.tools.ui.tui_app import (
    accept_completion,
    build_empty_reply_result,
    build_post_input_commands,
    build_status_fragments,
    build_submit_command,
    get_selected_waiting_input_run,
    has_active_completion,
    should_refresh_after_input,
    should_submit_on_enter,
)

pytestmark = pytest.mark.unit


def test_should_submit_on_enter_accepts_slash_command() -> None:
    assert should_submit_on_enter("/help") is True


def test_should_submit_on_enter_accepts_exit_keyword() -> None:
    assert should_submit_on_enter("exit") is True


def test_should_submit_on_enter_keeps_multiline_messages_editable() -> None:
    assert should_submit_on_enter("hola") is False
    assert should_submit_on_enter("hola\nmundo") is False


def test_should_submit_on_enter_accepts_plain_text_for_waiting_input() -> None:
    assert should_submit_on_enter("hola", waiting_input=True) is True


def test_has_active_completion_returns_false_without_completions() -> None:
    buffer = Buffer(document=Document("/h", cursor_position=2))

    assert has_active_completion(buffer) is False


def test_accept_completion_applies_first_suggestion_when_none_selected() -> None:
    buffer = Buffer(document=Document("/h", cursor_position=2))
    buffer.complete_state = CompletionState(
        original_document=buffer.document,
        completions=[Completion("/help", start_position=-2)],
        complete_index=None,
    )

    accepted = accept_completion(buffer)

    assert accepted is True
    assert buffer.text == "/help"


def test_accept_completion_returns_false_without_completion_state() -> None:
    buffer = Buffer(document=Document("/h", cursor_position=2))

    assert accept_completion(buffer) is False


def test_accept_completion_returns_false_outside_command_prefix() -> None:
    buffer = Buffer(document=Document("/input run-1 hola", cursor_position=17))
    buffer.complete_state = CompletionState(
        original_document=buffer.document,
        completions=[Completion("/input", start_position=-6)],
        complete_index=0,
    )

    assert accept_completion(buffer) is False


def test_build_status_fragments_marks_error_status() -> None:
    result = build_status_fragments("× Error")

    assert result == [("class:status.error", "× Error")]


def test_get_selected_waiting_input_run_returns_selected_waiting_run() -> None:
    session = UiSession(session_key="a1b2c3d4")
    session.runs.append(
        UiRun(
            raw_args="wait_input_test",
            run_id="run-1",
            status="WAITING",
            last_payload={"wait_type": "input", "prompt": "Write a short summary"},
        )
    )
    session.selected_run_id = "run-1"

    result = get_selected_waiting_input_run(session)

    assert result is not None
    assert result.run_id == "run-1"


def test_build_submit_command_routes_plain_text_to_waiting_input() -> None:
    session = UiSession(session_key="a1b2c3d4")
    session.runs.append(
        UiRun(
            raw_args="wait_input_test",
            run_id="run-1",
            status="WAITING",
            last_payload={"wait_type": "input", "prompt": "Write a short summary"},
        )
    )
    session.selected_run_id = "run-1"

    result = build_submit_command(session=session, text="database timeout")

    assert result == InputCommand(run_id="run-1", text="database timeout")


def test_build_submit_command_keeps_slash_commands_while_waiting_input() -> None:
    session = UiSession(session_key="a1b2c3d4")
    session.runs.append(
        UiRun(
            raw_args="wait_input_test",
            run_id="run-1",
            status="WAITING",
            last_payload={"wait_type": "input", "prompt": "Write a short summary"},
        )
    )
    session.selected_run_id = "run-1"

    result = build_submit_command(session=session, text="/status run-1")

    assert result == StatusCommand(run_id="run-1")


def test_build_empty_reply_result_uses_input_error_payload() -> None:
    run = UiRun(raw_args="wait_input_test", run_id="run-1", status="WAITING")

    result = build_empty_reply_result(run=run)

    assert result == ActionResult(
        kind="input",
        run=run,
        payload={"accepted": False, "error": "reply text is required"},
    )


def test_should_refresh_after_input_accepts_successful_input_result() -> None:
    result = ActionResult(
        kind="input",
        payload={"accepted": True, "matched_runs": ["run-1"]},
    )

    assert should_refresh_after_input(result) is True


def test_should_refresh_after_input_rejects_input_error_result() -> None:
    result = ActionResult(
        kind="input",
        payload={"accepted": False, "error": "reply text is required"},
    )

    assert should_refresh_after_input(result) is False


def test_build_post_input_commands_use_watch_and_status_for_same_run() -> None:
    result = build_post_input_commands(command=InputCommand(run_id="run-1", text="hola"))

    assert result == (
        WatchCommand(run_id="run-1"),
        StatusCommand(run_id="run-1"),
    )
