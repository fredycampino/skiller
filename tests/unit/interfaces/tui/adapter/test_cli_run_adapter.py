from __future__ import annotations

import subprocess

import pytest

import skiller.interfaces.tui.adapter.cli_run_adapter as cli_run_adapter_module
from skiller.interfaces.tui.adapter.cli_run_adapter import CliRunAdapter
from skiller.interfaces.tui.port.run_port import CommandAckStatus

pytestmark = pytest.mark.unit


def test_cli_run_adapter_rejects_empty_args() -> None:
    adapter = CliRunAdapter()

    result = adapter.run("")

    assert result.status == CommandAckStatus.REJECTED
    assert result.message == "error: /run requires arguments"


def test_cli_run_adapter_returns_dispatch_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        _ = args
        _ = kwargs
        return subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=0,
            stdout='{"run_id": "run-1234", "status": "CREATED"}',
            stderr="",
        )

    monkeypatch.setattr(cli_run_adapter_module.subprocess, "run", fake_run)

    adapter = CliRunAdapter()
    result = adapter.run("chat")

    assert result.status == CommandAckStatus.ACCEPTED
    assert result.run_id == "run-1234"
    assert result.message == "[run-dispatch] chat:1234\n  ↳ created"


def test_cli_run_adapter_returns_error_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        _ = args
        _ = kwargs
        return subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=1,
            stdout="",
            stderr="boom",
        )

    monkeypatch.setattr(cli_run_adapter_module.subprocess, "run", fake_run)

    adapter = CliRunAdapter()
    result = adapter.run("chat")

    assert result.status == CommandAckStatus.ERROR
    assert result.message == "error: boom"


def test_cli_run_adapter_sanitizes_skill_not_found_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        _ = args
        _ = kwargs
        return subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=1,
            stdout="",
            stderr=(
                "Traceback (most recent call last):\n"
                '  File "/tmp/x.py", line 1, in <module>\n'
                "FileNotFoundError: Skill not found: source=internal ref=av\n"
            ),
        )

    monkeypatch.setattr(cli_run_adapter_module.subprocess, "run", fake_run)

    adapter = CliRunAdapter()
    result = adapter.run("av")

    assert result.status == CommandAckStatus.ERROR
    assert result.message == "error: skill not found: av"
