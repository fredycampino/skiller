from __future__ import annotations

import pytest

from skiller.interfaces.ui.actions import ActionResult
from skiller.interfaces.ui.commands import (
    BodyCommand,
    LogsCommand,
    RunCommand,
    ServerStatusCommand,
    WatchCommand,
)
from skiller.interfaces.ui.session import UiRun, build_session
from skiller.interfaces.ui.tui_render import (
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


def test_render_result_for_buffer_renders_body_payload() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(
            kind="body",
            body_ref="execution_output:1",
            payload={"data": {"reply": "hola"}},
        ),
    )

    assert result.text == (
        "body_ref: execution_output:1\n"
        "{\n"
        '  "data": {\n'
        '    "reply": "hola"\n'
        "  }\n"
        "}\n"
    )
    assert result.replace is False


def test_render_result_for_buffer_renders_server_payload() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(
            kind="server",
            payload={
                "running": True,
                "managed": True,
                "endpoint": "http://127.0.0.1:8001/health",
                "pid": 12345,
            },
        ),
    )

    assert result.text == (
        "server\n"
        "  ✓ url: http://127.0.0.1:8001/health\n"
        "    pid: 12345\n"
        "    managed by skiller\n"
    )
    assert result.replace is False


def test_render_result_for_buffer_renders_webhooks_compact_list() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(
            kind="webhooks",
            webhooks=[
                {
                    "webhook": "signal",
                    "enabled": True,
                    "created_at": "2026-03-12 01:02:52",
                },
                {
                    "webhook": "test-token",
                    "enabled": True,
                    "created_at": "2026-03-08 23:28:33",
                },
            ],
        ),
    )

    assert result.text == (
        "webhooks\n"
        "  ✓ signal       2026-03-12 01:02:52\n"
        "  ✓ test-token   2026-03-08 23:28:33\n"
    )
    assert result.replace is False


def test_render_result_for_buffer_renders_runs_waiting_compact_list() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(
            kind="runs",
            statuses=["WAITING"],
            runs=[
                {
                    "id": "f25d21cc-95ea-4dc1-9305-c18f4ddceaca",
                    "status": "WAITING",
                    "skill_ref": "chat",
                    "current": "ask_user",
                    "wait_type": "input",
                },
                {
                    "id": "abcd1234-1111-2222-3333-444444444444",
                    "status": "WAITING",
                    "skill_ref": "deploy",
                    "current": "wait_signal",
                    "wait_type": "webhook",
                    "wait_detail": "github-ci:42",
                },
            ],
        ),
    )

    assert result.text == (
        "runs [waiting]\n"
        "  ◌ f25d21cc-95ea-4dc1-9305-c18f4ddceaca  chat  ask_user  input\n"
        "  ◌ abcd1234-1111-2222-3333-444444444444  deploy  wait_signal  webhook:[github-ci:42]\n"
    )
    assert result.replace is False


def test_render_result_for_buffer_renders_runs_with_file_skill_basename() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(
            kind="runs",
            runs=[
                {
                    "id": "023aa725-b4e8-4d02-a898-2422c16cdfaa",
                    "status": "WAITING",
                    "skill_ref": "tests/e2e/skills/wait_webhook_cli_e2e.yaml",
                    "current": "wait_signal",
                    "wait_type": "webhook",
                    "wait_detail": "test:demo-webhook-runs",
                }
            ],
        ),
    )

    assert result.text == (
        "runs\n"
        "  ◌ 023aa725-b4e8-4d02-a898-2422c16cdfaa  wait_webhook_cli_e2e.yaml  wait_signal  "
        "webhook:[test:demo-webhook-runs]\n"
    )
    assert result.replace is False


def test_build_pending_status_text_renders_loading_body() -> None:
    assert build_pending_status_text(command=BodyCommand(body_ref="execution_output:1")) == (
        "Loading body"
    )


def test_build_pending_status_text_renders_loading_server() -> None:
    assert build_pending_status_text(command=ServerStatusCommand()) == "Loading server"


def test_build_result_status_text_renders_loaded_body() -> None:
    assert build_result_status_text(
        result=ActionResult(
            kind="body",
            body_ref="execution_output:1",
            payload={"data": {"reply": "hola"}},
        )
    ) == "Loaded body"


def test_build_result_status_text_renders_loaded_server() -> None:
    assert build_result_status_text(
        result=ActionResult(kind="server", payload={"running": True})
    ) == "Loaded server"


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
                    "current": "ask_user",
                    "wait_type": "input",
                    "prompt": "Write a short summary",
                },
            ),
        ),
    )

    assert result.text == (
        "[run-create] wait_input_test:un-1\n"
        "  [wait_input] ask_user\n"
        "    Write a short summary\n"
    )
    assert result.replace is False


def test_render_result_for_buffer_renders_run_logs_for_succeeded_run() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(
            kind="run",
            run=UiRun(
                raw_args="repo_checks",
                run_id="12345678-1234-1234-1234-12345678ed0a",
                status="SUCCEEDED",
                logs=[
                    {"id": "evt-1", "type": "RUN_CREATE", "payload": {"skill_ref": "repo_checks"}},
                    {
                        "id": "evt-2",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "run_ruff",
                            "step_type": "shell",
                            "output": {
                                "text": "All checks passed!",
                                "value": {"ok": True, "exit_code": 0},
                                "body_ref": None,
                            },
                        },
                    },
                    {
                        "id": "evt-3",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "run_pytest",
                            "step_type": "shell",
                            "output": {
                                "text": "363 passed, 2 skipped",
                                "value": {"ok": True, "exit_code": 0},
                                "body_ref": None,
                            },
                        },
                    },
                ],
            ),
        ),
    )

    assert result.text == (
        "[run-create] repo_checks:ed0a\n"
        "  [shell] run_ruff\n"
        "    All checks passed!\n"
        "  [shell] run_pytest\n"
        "    363 passed, 2 skipped\n"
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
        "    [1]\n"
        "      {\n"
        '        "payload": {\n'
        '          "error": "network down",\n'
        '          "status": "FAILED"\n'
        "        },\n"
        '        "type": "RUN_FINISHED"\n'
        "      }\n"
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
                            "step": "ask_user",
                            "step_type": "wait_input",
                            "output": {
                                "text": "Write a message. Type exit, quit, or bye to stop.",
                                "value": {
                                    "prompt": "Write a message. Type exit, quit, or bye to stop."
                                },
                                "body_ref": None,
                            },
                        },
                    },
                    {
                        "id": "evt-2",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "answer",
                            "step_type": "llm_prompt",
                            "output": {
                                "text": "hola",
                                "value": {"data": {"reply": "hola"}},
                                "body_ref": None,
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
                            "output": {
                                "text": "hola",
                                "value": {"message": "hola"},
                                "body_ref": None,
                            },
                            "next": "ask_user",
                        },
                    },
                ],
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


def test_render_result_for_buffer_labels_waiting_watch_block_as_run_wait() -> None:
    session = build_session("a1b2c3d4")

    result = render_result_for_buffer(
        session=session,
        result=ActionResult(
            kind="watch",
            run=UiRun(
                raw_args="whatsapp_demo",
                run_id="12345678-1234-1234-1234-12345678e8f8",
                status="WAITING",
            ),
            payload={
                "events": [
                    {
                        "id": "evt-0",
                        "type": "RUN_CREATE",
                        "payload": {"skill_ref": "whatsapp_demo"},
                    },
                    {
                        "id": "evt-1",
                        "type": "RUN_WAITING",
                        "payload": {
                            "step": "listen_whatsapp",
                            "step_type": "wait_channel",
                            "output": {
                                "text": "Waiting channel: whatsapp:all.",
                                "value": {"channel": "whatsapp", "key": "all"},
                                "body_ref": None,
                            },
                        },
                    },
                ],
            },
        ),
    )

    assert result.text == (
        "[run-wait] whatsapp_demo:e8f8\n"
        "  [wait_channel] listen_whatsapp\n"
        "    Waiting channel: whatsapp:all.\n"
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
                            "step": "ask_user",
                            "step_type": "wait_input",
                            "output": {
                                "text": "Write a message.",
                                "value": {"prompt": "Write a message."},
                                "body_ref": None,
                            },
                        },
                    },
                    {
                        "id": "evt-1",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "ask_user",
                            "step_type": "wait_input",
                            "output": {
                                "text": "Input received.",
                                "value": {
                                    "prompt": "Write a message.",
                                    "payload": {"text": "hola"},
                                },
                                "body_ref": None,
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
                            "output": {
                                "text": "answer",
                                "value": {"next_step_id": "answer"},
                                "body_ref": None,
                            },
                            "next": "answer",
                        },
                    },
                    {
                        "id": "evt-3",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "answer",
                            "step_type": "llm_prompt",
                            "output": {
                                "text": "hola",
                                "value": {"data": {"reply": "hola"}},
                                "body_ref": None,
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
                            "output": {
                                "text": "hola",
                                "value": {"message": "hola"},
                                "body_ref": None,
                            },
                            "next": "ask_user",
                        },
                    },
                    {
                        "id": "evt-5",
                        "type": "RUN_WAITING",
                        "payload": {
                            "step": "ask_user",
                            "step_type": "wait_input",
                            "output": {
                                "text": "Write a message.",
                                "value": {"prompt": "Write a message."},
                                "body_ref": None,
                            },
                        },
                    },
                ],
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
        "  [wait_input] ask_user\n"
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
                        "payload": {"step": "ask_user", "step_type": "wait_input"},
                    },
                    {
                        "id": "evt-2",
                        "type": "RUN_WAITING",
                        "payload": {
                            "step": "ask_user",
                            "step_type": "wait_input",
                            "output": {
                                "text": "Write a message. Type exit, quit, or bye to stop.",
                                "value": {
                                    "prompt": "Write a message. Type exit, quit, or bye to stop."
                                },
                                "body_ref": None,
                            },
                        },
                    },
                    {
                        "id": "evt-3",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "decide_exit",
                            "step_type": "switch",
                            "output": {
                                "text": "answer",
                                "value": {"next_step_id": "answer"},
                                "body_ref": None,
                            },
                        },
                    },
                    {
                        "id": "evt-4",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "answer",
                            "step_type": "llm_prompt",
                            "output": {
                                "text": "España tiene 50 provincias.",
                                "value": None,
                                "body_ref": None,
                            },
                        },
                    },
                    {
                        "id": "evt-5",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "show_reply",
                            "step_type": "notify",
                            "output": {
                                "text": "España tiene 50 provincias.",
                                "value": {"message": "España tiene 50 provincias."},
                                "body_ref": None,
                            },
                        },
                    },
                    {
                        "id": "evt-6",
                        "type": "RUN_WAITING",
                        "payload": {
                            "step": "ask_user",
                            "step_type": "wait_input",
                            "output": {
                                "text": "Write a message. Type exit, quit, or bye to stop.",
                                "value": {
                                    "prompt": "Write a message. Type exit, quit, or bye to stop."
                                },
                                "body_ref": None,
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
        "  [wait_input] ask_user\n"
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
                            "output": {
                                "text": (
                                    "Según los datos más recientes, "
                                    "España tiene 48 millones."
                                ),
                                "value": {
                                    "message": (
                                        "Según los datos más recientes, "
                                        "España tiene 48 millones."
                                    )
                                },
                                "body_ref": None,
                            },
                            "next": "ask_user",
                        },
                    },
                    {
                        "id": "evt-2",
                        "type": "RUN_WAITING",
                        "payload": {
                            "step": "ask_user",
                            "step_type": "wait_input",
                            "output": {
                                "text": "Write a message.",
                                "value": {"prompt": "Write a message."},
                                "body_ref": None,
                            },
                        },
                    },
                ],
            },
        ),
    )

    assert result.text == (
        "[run-resume] chat:f28a\n"
        "  [notify] show_reply\n"
        "    Según los datos más recientes, España tiene 48 millones.\n"
        "  [wait_input] ask_user\n"
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
                            "output": {
                                "text": '"Seg\\u00fan los datos m\\u00e1s recientes, '
                                'Espa\\u00f1a tiene 48 millones."',
                                "value": {
                                    "message": '"Seg\\u00fan los datos m\\u00e1s recientes, '
                                    'Espa\\u00f1a tiene 48 millones."'
                                },
                                "body_ref": None,
                            },
                            "next": "ask_user",
                        },
                    },
                    {
                        "id": "evt-2",
                        "type": "RUN_WAITING",
                        "payload": {
                            "step": "ask_user",
                            "step_type": "wait_input",
                            "output": {
                                "text": "Write a message.",
                                "value": {"prompt": "Write a message."},
                                "body_ref": None,
                            },
                        },
                    },
                ],
            },
        ),
    )

    assert result.text == (
        "[run-resume] chat:5e13\n"
        "  [notify] show_reply\n"
        "    Según los datos más recientes, España tiene 48 millones.\n"
        "  [wait_input] ask_user\n"
        "    Write a message.\n"
    )
    assert result.replace is False


def test_render_result_for_buffer_wraps_long_notify_detail_without_breaking_words() -> None:
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
                            "output": {
                                "text": (
                                    "En la naturaleza, un leon vive entre 10 y 14 anos. "
                                    "En cautiverio, pueden vivir hasta 20 anos o mas "
                                    "gracias a los cuidados veterinarios y la alimentacion "
                                    "constante."
                                ),
                                "value": {
                                    "message": (
                                        "En la naturaleza, un leon vive entre 10 y 14 anos. "
                                        "En cautiverio, pueden vivir hasta 20 anos o mas "
                                        "gracias a los cuidados veterinarios y la alimentacion "
                                        "constante."
                                    )
                                },
                                "body_ref": None,
                            },
                            "next": "start",
                        },
                    }
                ]
            },
        ),
    )

    assert "    En la naturaleza, un leon vive entre 10 y 14 anos." in result.text
    assert "    pueden vivir hasta 20 anos o mas gracias a los cuidados veterinarios" in result.text
    assert "    y la alimentacion constante." in result.text
    assert " ano\n" not in result.text


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


def test_build_result_status_text_uses_waiting_input_label() -> None:
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

    assert result == "Waiting → input"


def test_build_result_status_text_uses_waiting_webhook_label() -> None:
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

    assert result == "Waiting → webhook"


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
                last_payload={"error": "database timeout"},
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
                last_payload={"error": "LLM is not configured for llm_prompt steps"},
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
        status_text="Waiting → input",
        now=0.0,
    )

    assert result == "◌ Waiting → input"


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
