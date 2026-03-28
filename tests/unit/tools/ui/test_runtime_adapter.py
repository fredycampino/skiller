from __future__ import annotations

import json
import subprocess

import pytest

from skiller.tools.ui import runtime_adapter

pytestmark = pytest.mark.unit


def test_execute_run_invokes_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        recorded["cmd"] = cmd
        recorded["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps({"run_id": "run-1", "status": "SUCCEEDED"}),
            stderr="",
        )

    monkeypatch.setattr(runtime_adapter.subprocess, "run", fake_run)

    result = runtime_adapter.execute_run(raw_args="notify_test --arg foo=bar")

    assert result == {"run_id": "run-1", "status": "SUCCEEDED"}
    assert recorded["cmd"] == [
        runtime_adapter.sys.executable,
        "-m",
        "skiller",
        "run",
        "notify_test",
        "--arg",
        "foo=bar",
    ]


def test_execute_run_preserves_start_webhooks_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        recorded["cmd"] = cmd
        recorded["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps({"run_id": "run-2", "status": "WAITING"}),
            stderr="",
        )

    monkeypatch.setattr(runtime_adapter.subprocess, "run", fake_run)

    result = runtime_adapter.execute_run(
        raw_args="--file tests/e2e/skills/wait_webhook_cli_e2e.yaml --arg key=42 --start-webhooks",
    )

    assert result == {"run_id": "run-2", "status": "WAITING"}
    assert recorded["cmd"] == [
        runtime_adapter.sys.executable,
        "-m",
        "skiller",
        "run",
        "--file",
        "tests/e2e/skills/wait_webhook_cli_e2e.yaml",
        "--arg",
        "key=42",
        "--start-webhooks",
    ]


def test_execute_run_rejects_empty_args() -> None:
    with pytest.raises(RuntimeError, match="run command requires skill args"):
        runtime_adapter.execute_run(raw_args="   ")


def test_execute_run_raises_when_command_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")

    monkeypatch.setattr(runtime_adapter.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="boom"):
        runtime_adapter.execute_run(raw_args="notify_test")


def test_cli_runtime_adapter_status_invokes_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        recorded["cmd"] = cmd
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps({"id": "run-1", "status": "WAITING"}),
            stderr="",
        )

    monkeypatch.setattr(runtime_adapter.subprocess, "run", fake_run)

    adapter = runtime_adapter.CliRuntimeAdapter()
    result = adapter.status(run_id="run-1")

    assert result == {"id": "run-1", "status": "WAITING"}
    assert recorded["cmd"] == [
        runtime_adapter.sys.executable,
        "-m",
        "skiller",
        "status",
        "run-1",
    ]


def test_cli_runtime_adapter_runs_invokes_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        recorded["cmd"] = cmd
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps(
                [
                    {
                        "id": "run-1",
                        "status": "WAITING",
                        "skill_ref": "notify_test",
                        "current": "start",
                    }
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr(runtime_adapter.subprocess, "run", fake_run)

    adapter = runtime_adapter.CliRuntimeAdapter()
    result = adapter.runs()

    assert result == [
        {
            "id": "run-1",
            "status": "WAITING",
            "skill_ref": "notify_test",
            "current": "start",
        }
    ]
    assert recorded["cmd"] == [
        runtime_adapter.sys.executable,
        "-m",
        "skiller",
        "runs",
    ]


def test_cli_runtime_adapter_runs_preserves_status_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        recorded["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")

    monkeypatch.setattr(runtime_adapter.subprocess, "run", fake_run)

    adapter = runtime_adapter.CliRuntimeAdapter()
    result = adapter.runs(statuses=["WAITING", "FAILED"])

    assert result == []
    assert recorded["cmd"] == [
        runtime_adapter.sys.executable,
        "-m",
        "skiller",
        "runs",
        "--status",
        "WAITING",
        "--status",
        "FAILED",
    ]


def test_cli_runtime_adapter_webhooks_invokes_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        recorded["cmd"] = cmd
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps(
                [
                    {
                        "webhook": "github-ci",
                        "enabled": True,
                        "created_at": "2026-03-19 10:00:00",
                    }
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr(runtime_adapter.subprocess, "run", fake_run)

    adapter = runtime_adapter.CliRuntimeAdapter()
    result = adapter.webhooks()

    assert result == [
        {
            "webhook": "github-ci",
            "enabled": True,
            "created_at": "2026-03-19 10:00:00",
        }
    ]
    assert recorded["cmd"] == [
        runtime_adapter.sys.executable,
        "-m",
        "skiller",
        "webhook",
        "list",
    ]


def test_cli_runtime_adapter_logs_invokes_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps([{"id": "evt-1", "type": "NOTIFY", "payload": {}}]),
            stderr="",
        )

    monkeypatch.setattr(runtime_adapter.subprocess, "run", fake_run)

    adapter = runtime_adapter.CliRuntimeAdapter()
    result = adapter.logs(run_id="run-1")

    assert result == [{"id": "evt-1", "type": "NOTIFY", "payload": {}}]


def test_cli_runtime_adapter_watch_captures_events_text(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps(
                {
                    "run_id": "run-1",
                    "status": "WAITING",
                    "events": [
                        {
                            "id": "evt-1",
                            "type": "RUN_WAITING",
                            "payload": {
                                "step": "start",
                                "step_type": "wait_input",
                                "result": {"prompt": "Write a message."},
                            },
                        }
                    ],
                }
            ),
            stderr=(
                '[1234] RUN_WAITING step="start" step_type="wait_input" '
                'result={"prompt":"Write a message."}'
            ),
        )

    monkeypatch.setattr(runtime_adapter.subprocess, "run", fake_run)

    adapter = runtime_adapter.CliRuntimeAdapter()
    result = adapter.watch(run_id="run-1")

    assert result == {
        "run_id": "run-1",
        "status": "WAITING",
        "events": [
            {
                "id": "evt-1",
                "type": "RUN_WAITING",
                "payload": {
                    "step": "start",
                    "step_type": "wait_input",
                    "result": {"prompt": "Write a message."},
                },
            }
        ],
        "events_text": (
            '[1234] RUN_WAITING step="start" step_type="wait_input" '
            'result={"prompt":"Write a message."}'
        ),
    }


def test_cli_runtime_adapter_watch_accepts_failed_terminal_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(cmd, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(
            cmd,
            1,
            stdout=json.dumps(
                {
                    "run_id": "run-1",
                    "status": "FAILED",
                    "events": [
                        {
                            "id": "evt-2",
                            "type": "STEP_ERROR",
                            "payload": {
                                "step": "answer",
                                "step_type": "llm_prompt",
                                "error": "network down",
                            },
                        }
                    ],
                }
            ),
            stderr='[1234] RUN_FINISHED status="FAILED" error="network down"',
        )

    monkeypatch.setattr(runtime_adapter.subprocess, "run", fake_run)

    adapter = runtime_adapter.CliRuntimeAdapter()
    result = adapter.watch(run_id="run-1")

    assert result == {
        "run_id": "run-1",
        "status": "FAILED",
        "events": [
            {
                "id": "evt-2",
                "type": "STEP_ERROR",
                "payload": {
                    "step": "answer",
                    "step_type": "llm_prompt",
                    "error": "network down",
                },
            }
        ],
        "events_text": '[1234] RUN_FINISHED status="FAILED" error="network down"',
    }


def test_cli_runtime_adapter_input_receive_invokes_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        recorded["cmd"] = cmd
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps({"accepted": True, "matched_runs": ["run-1"]}),
            stderr="",
        )

    monkeypatch.setattr(runtime_adapter.subprocess, "run", fake_run)

    adapter = runtime_adapter.CliRuntimeAdapter()
    result = adapter.input_receive(run_id="run-1", text="hola")

    assert result == {"accepted": True, "matched_runs": ["run-1"]}
    assert recorded["cmd"] == [
        runtime_adapter.sys.executable,
        "-m",
        "skiller",
        "input",
        "receive",
        "run-1",
        "--text",
        "hola",
    ]


def test_cli_runtime_adapter_resume_invokes_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        recorded["cmd"] = cmd
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps({"run_id": "run-1", "resume_status": "DISPATCHED"}),
            stderr="",
        )

    monkeypatch.setattr(runtime_adapter.subprocess, "run", fake_run)

    adapter = runtime_adapter.CliRuntimeAdapter()
    result = adapter.resume(run_id="run-1")

    assert result == {"run_id": "run-1", "resume_status": "DISPATCHED"}
    assert recorded["cmd"] == [
        runtime_adapter.sys.executable,
        "-m",
        "skiller",
        "resume",
        "run-1",
    ]
