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
