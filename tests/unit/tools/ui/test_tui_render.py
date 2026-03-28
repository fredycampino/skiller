from __future__ import annotations

import pytest

from skiller.tools.ui.actions import ActionResult
from skiller.tools.ui.commands import LogsCommand, RunCommand, WatchCommand
from skiller.tools.ui.session import UiRun, build_session
from skiller.tools.ui.tui_render import (
    build_footer_line,
    build_header_meta_line,
    build_header_title_line,
    build_initial_output,
    build_pending_input_status_text,
    build_pending_status_text,
    build_result_status_text,
    build_status_line,
    render_result_for_buffer,
)

pytestmark = pytest.mark.unit


def test_build_initial_output_renders_welcome_banner() -> None:
    session = build_session("a1b2c3d4")

    result = build_initial_output(session=session)

    assert result == ""


def test_render_result_for_buffer_clears_output_for_clear_action() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(session=session, result=ActionResult(kind="clear"))

    assert result.text == ""
    assert result.replace is True


def test_render_result_for_buffer_uses_existing_renderer_for_echo() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(kind="echo", message="hola"),
    )

    assert result.text == "[a1b2c3d4] echo: hola\n"
    assert result.replace is False


def test_render_result_for_buffer_renders_waiting_run_metadata() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(
            kind="run",
            run=UiRun(
                raw_args="wait_input_test",
                run_id="run-1",
                status="WAITING",
                last_payload={
                    "wait_type": "input",
                    "prompt": "Write a short summary",
                },
            ),
        ),
    )

    assert result.text == (
        "[run-create] wait_input_test:un-1\n"
        "  [wait_input] start\n"
        "    Write a short summary\n"
    )
    assert result.replace is False


def test_render_result_for_buffer_summarizes_traceback_error() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(
            kind="run",
            run=UiRun(
                raw_args="wating_input",
                status="FAILED",
                error=(
                    "Traceback (most recent call last):\n"
                    '  File "/tmp/demo.py", line 1, in <module>\n'
                    '    raise FileNotFoundError('
                    '"Skill not found: source=internal ref=wating_input")\n'
                    "FileNotFoundError: Skill not found: source=internal ref=wating_input"
                ),
            ),
        ),
    )

    assert result.text == (
        "[run-create] wating_input:-\n"
        "  ↳ error\n"
        "    Skill not found: source=internal ref=wating_input\n"
    )
    assert result.replace is False


def test_render_result_for_buffer_renders_input_error() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(
            kind="input",
            run=UiRun(raw_args="wait_input_test", run_id="run-1", status="WAITING"),
            payload={"accepted": False, "error": "reply text is required"},
        ),
    )

    assert result.text == (
        "run-un-1: wait_input_test\n"
        "  ↳ input rejected\n"
        "    reply text is required\n"
    )
    assert result.replace is False


def test_render_result_for_buffer_prefers_error_field_over_failed_watch_line() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(
            kind="watch",
            run=UiRun(
                raw_args="chat",
                run_id="12345678-1234-1234-1234-1234567883b6",
                status="FAILED",
            ),
            payload={
                "events": [
                    {
                        "id": "evt-1",
                        "type": "STEP_ERROR",
                        "payload": {
                            "step": "answer",
                            "step_type": "llm_prompt",
                            "error": "LLM is not configured for llm_prompt steps",
                        },
                    },
                    {
                        "id": "evt-2",
                        "type": "RUN_FINISHED",
                        "payload": {
                            "status": "FAILED",
                            "error": "LLM is not configured for llm_prompt steps",
                        },
                    },
                ]
            },
        ),
    )

    assert result.text == (
        "[run-resume] chat:83b6\n"
        "  ↳ error\n"
        "    LLM is not configured for llm_prompt steps\n"
    )
    assert result.replace is False


def test_render_result_for_buffer_deduplicates_identical_watch_errors() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(
            kind="watch",
            run=UiRun(
                raw_args="chat",
                run_id="12345678-1234-1234-1234-12345678c3b7",
                status="FAILED",
            ),
            payload={
                "events": [
                    {
                        "id": "evt-1",
                        "type": "STEP_ERROR",
                        "payload": {
                            "step": "answer",
                            "step_type": "llm_prompt",
                            "error": "network down",
                        },
                    },
                    {
                        "id": "evt-2",
                        "type": "RUN_FINISHED",
                        "payload": {
                            "status": "FAILED",
                            "error": "network down",
                        },
                    },
                ]
            },
        ),
    )

    assert result.text == (
        "[run-resume] chat:c3b7\n"
        "  ↳ error\n"
        "    network down\n"
    )
    assert result.replace is False


def test_render_result_for_buffer_renders_logs_error_block() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(
            kind="logs",
            run=UiRun(
                raw_args="logs",
                status="FAILED",
                error="No selected or last run is available for /logs",
            ),
            logs=[],
        ),
    )

    assert result.text == (
        "run: logs\n"
        "  ↳ error\n"
        "    No selected or last run is available for /logs\n"
    )
    assert result.replace is False


def test_render_result_for_buffer_renders_logs_for_failed_run() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(
            kind="logs",
            run=UiRun(
                raw_args="chat",
                run_id="run-1",
                status="FAILED",
            ),
            logs=[
                {
                    "type": "RUN_FINISHED",
                    "payload": {"status": "FAILED", "error": "network down"},
                }
            ],
        ),
    )

    assert result.text == (
        "run-un-1: chat\n"
        "  ↳ logs\n"
        "    count: 1\n"
        '    [1] RUN_FINISHED payload={"error": "network down", "status": "FAILED"}\n'
    )
    assert result.replace is False


def test_render_result_for_buffer_renders_semantic_watch_blocks() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(
            kind="watch",
            run=UiRun(
                raw_args="chat",
                run_id="12345678-1234-1234-1234-12345678aa95",
                status="WAITING",
            ),
            payload={
                "events": [
                    {
                        "id": "evt-1",
                        "type": "RUN_WAITING",
                        "payload": {
                            "step": "start",
                            "step_type": "wait_input",
                            "result": {
                                "prompt": "Write a message. Type exit, quit, or bye to stop."
                            },
                        },
                    },
                    {
                        "id": "evt-2",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "answer",
                            "step_type": "llm_prompt",
                            "result": {
                                "text": "hola",
                                "json": {"reply": "hola"},
                                "model": "MiniMax-M2.5",
                            },
                            "next": "show_reply",
                        },
                    },
                    {
                        "id": "evt-3",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "show_reply",
                            "step_type": "notify",
                            "result": {"message": "hola"},
                            "next": "start",
                        },
                    },
                ],
                "events_text": (
                    '[aa95] RUN_WAITING step="start" step_type="wait_input" '
                    'result={"prompt":"Write a message. Type exit, quit, or bye to stop."}\n'
                    '[aa95] STEP_SUCCESS step="answer" step_type="llm_prompt" '
                    'result={"text":"hola","json":{"reply":"hola"},'
                    '"model":"MiniMax-M2.5"} next="show_reply"\n'
                    '[aa95] STEP_SUCCESS step="show_reply" step_type="notify" '
                    'result={"message":"hola"} next="start"\n'
                    '[aa95] RUN_FINISHED status="WAITING"\n'
                )
            },
        ),
    )

    assert result.text == (
        "[run-resume] chat:aa95\n"
        "  [llm_prompt] answer\n"
        "    hola\n"
        "  [notify] show_reply\n"
        "    hola\n"
    )
    assert result.replace is False


def test_render_result_for_buffer_skips_resolved_wait_input_step_success() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(
            kind="watch",
            run=UiRun(
                raw_args="chat",
                run_id="12345678-1234-1234-1234-1234567815a0",
                status="WAITING",
            ),
            payload={
                "events": [
                    {
                        "id": "evt-0",
                        "type": "RUN_WAITING",
                        "payload": {
                            "step": "start",
                            "step_type": "wait_input",
                            "result": {"prompt": "Write a message."},
                        },
                    },
                    {
                        "id": "evt-1",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "start",
                            "step_type": "wait_input",
                            "result": {
                                "prompt": "Write a message.",
                                "payload": {"text": "hola"},
                                "input_event_id": "evt-1",
                            },
                            "next": "decide_exit",
                        },
                    },
                    {
                        "id": "evt-2",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "decide_exit",
                            "step_type": "switch",
                            "result": {"next": "answer"},
                            "next": "answer",
                        },
                    },
                    {
                        "id": "evt-3",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "answer",
                            "step_type": "llm_prompt",
                            "result": {
                                "text": "hola",
                                "json": {"reply": "hola"},
                                "model": "MiniMax-M2.5",
                            },
                            "next": "show_reply",
                        },
                    },
                    {
                        "id": "evt-4",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "show_reply",
                            "step_type": "notify",
                            "result": {"message": "hola"},
                            "next": "start",
                        },
                    },
                    {
                        "id": "evt-5",
                        "type": "RUN_WAITING",
                        "payload": {
                            "step": "start",
                            "step_type": "wait_input",
                            "result": {"prompt": "Write a message."},
                        },
                    },
                ],
                "events_text": (
                    '[15a0] STEP_SUCCESS step="start" step_type="wait_input" '
                    'result={"prompt":"Write a message.","payload":{"text":"hola"},'
                    '"input_event_id":"evt-1"} next="decide_exit"\n'
                    '[15a0] STEP_SUCCESS step="decide_exit" step_type="switch" '
                    'result={"next":"answer"} next="answer"\n'
                    '[15a0] STEP_SUCCESS step="answer" step_type="llm_prompt" '
                    'result={"text":"hola","json":{"reply":"hola"},'
                    '"model":"MiniMax-M2.5"} next="show_reply"\n'
                    '[15a0] STEP_SUCCESS step="show_reply" step_type="notify" '
                    'result={"message":"hola"} next="start"\n'
                    '[15a0] RUN_WAITING step="start" step_type="wait_input" '
                    'result={"prompt":"Write a message."}\n'
                    '[15a0] RUN_FINISHED status="WAITING"\n'
                )
            },
        ),
    )

    assert result.text == (
        "[run-resume] chat:15a0\n"
        "  [switch] decide_exit\n"
        "    answer\n"
        "  [llm_prompt] answer\n"
        "    hola\n"
        "  [notify] show_reply\n"
        "    hola\n"
        "  [wait_input] start\n"
        "    Write a message.\n"
    )
    assert result.replace is False


def test_render_result_for_buffer_skips_initial_waiting_after_resume_markers() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(
            kind="watch",
            run=UiRun(
                raw_args="chat",
                run_id="12345678-1234-1234-1234-123456787f1f",
                status="WAITING",
            ),
            payload={
                "events": [
                    {
                        "id": "evt-0",
                        "type": "RUN_RESUME",
                        "payload": {"source": "manual"},
                    },
                    {
                        "id": "evt-1",
                        "type": "STEP_STARTED",
                        "payload": {"step": "start", "step_type": "wait_input"},
                    },
                    {
                        "id": "evt-2",
                        "type": "RUN_WAITING",
                        "payload": {
                            "step": "start",
                            "step_type": "wait_input",
                            "result": {
                                "prompt": "Write a message. Type exit, quit, or bye to stop."
                            },
                        },
                    },
                    {
                        "id": "evt-3",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "decide_exit",
                            "step_type": "switch",
                            "result": {"next": "answer"},
                        },
                    },
                    {
                        "id": "evt-4",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "answer",
                            "step_type": "llm_prompt",
                            "result": {"text": "España tiene 50 provincias."},
                        },
                    },
                    {
                        "id": "evt-5",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "show_reply",
                            "step_type": "notify",
                            "result": {"message": "España tiene 50 provincias."},
                        },
                    },
                    {
                        "id": "evt-6",
                        "type": "RUN_WAITING",
                        "payload": {
                            "step": "start",
                            "step_type": "wait_input",
                            "result": {
                                "prompt": "Write a message. Type exit, quit, or bye to stop."
                            },
                        },
                    },
                ],
            },
        ),
    )

    assert result.text == (
        "[run-resume] chat:7f1f\n"
        "  [switch] decide_exit\n"
        "    answer\n"
        "  [llm_prompt] answer\n"
        "    España tiene 50 provincias.\n"
        "  [notify] show_reply\n"
        "    España tiene 50 provincias.\n"
        "  [wait_input] start\n"
        "    Write a message. Type exit, quit, or bye to stop.\n"
    )
    assert result.replace is False


def test_render_result_for_buffer_decodes_unicode_in_watch_notify_message() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(
            kind="watch",
            run=UiRun(
                raw_args="chat",
                run_id="12345678-1234-1234-1234-12345678f28a",
                status="WAITING",
            ),
            payload={
                "events": [
                    {
                        "id": "evt-1",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "show_reply",
                            "step_type": "notify",
                            "result": {
                                "message": (
                                    "Según los datos más recientes, "
                                    "España tiene 48 millones."
                                )
                            },
                            "next": "start",
                        },
                    },
                    {
                        "id": "evt-2",
                        "type": "RUN_WAITING",
                        "payload": {
                            "step": "start",
                            "step_type": "wait_input",
                            "result": {"prompt": "Write a message."},
                        },
                    },
                ],
                "events_text": (
                    '[f28a] STEP_SUCCESS step="show_reply" step_type="notify" '
                    'result={"message":"Seg\\u00fan los datos m\\u00e1s recientes, '
                    'Espa\\u00f1a tiene 48 millones."} next="start"\n'
                    '[f28a] RUN_WAITING step="start" step_type="wait_input" '
                    'result={"prompt":"Write a message."}\n'
                    '[f28a] RUN_FINISHED status="WAITING"\n'
                )
            },
        ),
    )

    assert result.text == (
        "[run-resume] chat:f28a\n"
        "  [notify] show_reply\n"
        "    Según los datos más recientes, España tiene 48 millones.\n"
        "  [wait_input] start\n"
        "    Write a message.\n"
    )
    assert result.replace is False


def test_render_result_for_buffer_decodes_double_escaped_unicode_in_watch_notify_message() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(
            kind="watch",
            run=UiRun(
                raw_args="chat",
                run_id="12345678-1234-1234-1234-123456785e13",
                status="WAITING",
            ),
            payload={
                "events": [
                    {
                        "id": "evt-1",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "show_reply",
                            "step_type": "notify",
                            "result": {
                                "message": '"Seg\\u00fan los datos m\\u00e1s recientes, '
                                'Espa\\u00f1a tiene 48 millones."'
                            },
                            "next": "start",
                        },
                    },
                    {
                        "id": "evt-2",
                        "type": "RUN_WAITING",
                        "payload": {
                            "step": "start",
                            "step_type": "wait_input",
                            "result": {"prompt": "Write a message."},
                        },
                    },
                ],
                "events_text": (
                    '[5e13] STEP_SUCCESS step="show_reply" step_type="notify" '
                    'result={"message":"\\"Seg\\\\u00fan los datos m\\\\u00e1s recientes, '
                    'Espa\\\\u00f1a tiene 48 millones.\\""} next="start"\n'
                    '[5e13] RUN_WAITING step="start" step_type="wait_input" '
                    'result={"prompt":"Write a message."}\n'
                    '[5e13] RUN_FINISHED status="WAITING"\n'
                )
            },
        ),
    )

    assert result.text == (
        "[run-resume] chat:5e13\n"
        "  [notify] show_reply\n"
        "    Según los datos más recientes, España tiene 48 millones.\n"
        "  [wait_input] start\n"
        "    Write a message.\n"
    )
    assert result.replace is False


def test_build_header_title_line_exposes_brand_and_session() -> None:
    session = build_session("a1b2c3d4")

    result = build_header_title_line(session=session)

    assert result == "[ Skiller ]                               session: a1b2c3d4"


def test_build_header_meta_line_exposes_selected_run() -> None:
    session = build_session("a1b2c3d4")
    session.selected_run_id = "run-1"

    result = build_header_meta_line(session=session)

    assert result == "Run Console                               selected: run-1"


def test_build_pending_status_text_uses_action_specific_labels() -> None:
    assert (
        build_pending_status_text(command=RunCommand(raw_args="notify_test"))
        == "Running notify_test"
    )
    assert build_pending_status_text(command=WatchCommand(run_id="run-1")) == "Watching"
    assert build_pending_status_text(command=LogsCommand(run_id="run-1")) == "Loading logs"


def test_build_pending_input_status_text_uses_run_label() -> None:
    result = build_pending_input_status_text(
        run=UiRun(raw_args="chat", run_id="run-1", status="WAITING")
    )

    assert result == "Running chat"


def test_build_result_status_text_uses_waiting_input_prompt() -> None:
    result = build_result_status_text(
        result=ActionResult(
            kind="run",
            run=UiRun(
                raw_args="wait_input_test",
                run_id="run-1",
                status="WAITING",
                last_payload={"wait_type": "input", "prompt": "Write a short summary"},
            ),
        )
    )

    assert result == "Waiting → Write a short summary"


def test_build_result_status_text_uses_waiting_webhook_name() -> None:
    result = build_result_status_text(
        result=ActionResult(
            kind="status",
            run=UiRun(
                raw_args="wait_webhook_test",
                run_id="run-1",
                status="WAITING",
                last_payload={"wait_type": "webhook", "webhook": "github-pr-merged", "key": "42"},
            ),
        )
    )

    assert result == "Waiting github-pr-merged"


def test_build_result_status_text_uses_running_run_label() -> None:
    result = build_result_status_text(
        result=ActionResult(
            kind="watch",
            run=UiRun(raw_args="notify_test", run_id="run-1", status="RUNNING"),
        )
    )

    assert result == "Running notify_test"


def test_build_result_status_text_uses_success_run_label() -> None:
    result = build_result_status_text(
        result=ActionResult(
            kind="watch",
            run=UiRun(raw_args="notify_test", run_id="run-1", status="SUCCEEDED"),
        )
    )

    assert result == "Success notify_test"


def test_build_result_status_text_uses_error_message() -> None:
    result = build_result_status_text(
        result=ActionResult(
            kind="watch",
            run=UiRun(
                raw_args="notify_test",
                run_id="run-1",
                status="FAILED",
                last_payload={
                    "events_text": (
                        '[1234] RUN_FINISHED status="FAILED" '
                        'error="database timeout"'
                    )
                },
            ),
        )
    )

    assert result == "Error"


def test_build_result_status_text_summarizes_traceback_error() -> None:
    result = build_result_status_text(
        result=ActionResult(
            kind="run",
            run=UiRun(
                raw_args="wating_input",
                status="FAILED",
                error=(
                    "Traceback (most recent call last):\n"
                    '  File "/tmp/demo.py", line 1, in <module>\n'
                    "FileNotFoundError: Skill not found: source=internal ref=wating_input"
                ),
            ),
        )
    )

    assert result == "Error"


def test_build_result_status_text_prefers_error_field_over_failed_watch_line() -> None:
    result = build_result_status_text(
        result=ActionResult(
            kind="watch",
            run=UiRun(
                raw_args="chat",
                run_id="12345678-1234-1234-1234-1234567883b6",
                status="FAILED",
                last_payload={
                    "events_text": (
                        '[83b6] STEP_ERROR step="answer" step_type="llm_prompt" '
                        'error="LLM is not configured for llm_prompt steps"\n'
                        '[83b6] RUN_FINISHED status="FAILED" '
                        'error="LLM is not configured for llm_prompt steps"'
                    )
                },
            ),
        )
    )

    assert result == "Error"


def test_build_result_status_text_uses_loaded_counts() -> None:
    result = build_result_status_text(
        result=ActionResult(
            kind="runs",
            runs=[
                {"id": "run-1"},
                {"id": "run-2"},
            ],
        )
    )

    assert result == "Loaded 2 runs"


def test_build_status_line_exposes_progress_for_idle_status() -> None:
    session = build_session("a1b2c3d4")

    result = build_status_line(session=session, status_text="Idle", now=0.0)

    assert result == "· Idle"


def test_build_status_line_exposes_spinner_when_busy() -> None:
    session = build_session("a1b2c3d4")

    result = build_status_line(session=session, status_text="Processing", busy=True, now=0.0)

    assert result == "◐ Processing"


def test_build_status_line_formats_waiting_status() -> None:
    session = build_session("a1b2c3d4")

    result = build_status_line(
        session=session,
        status_text="Waiting → Write a short summary",
        now=0.0,
    )

    assert result == "◌ Waiting → Write a short summary"


def test_build_status_line_formats_success_status() -> None:
    session = build_session("a1b2c3d4")

    result = build_status_line(session=session, status_text="Success notify_test", now=0.0)

    assert result == "✓ Success notify_test"


def test_build_status_line_formats_error_status() -> None:
    session = build_session("a1b2c3d4")

    result = build_status_line(session=session, status_text="Error", now=0.0)

    assert result == "× Error"


def test_build_footer_line_exposes_last_run_and_shortcuts() -> None:
    session = build_session("a1b2c3d4")
    session.last_run_id = "run-2"

    result = build_footer_line(session=session)

    assert result == "  last=run-2 | Enter command | Ctrl+C exit"
