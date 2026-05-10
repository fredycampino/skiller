from __future__ import annotations

import subprocess
from dataclasses import dataclass

import pytest
from stui.adapter.cli_run_adapter import CliRunAdapter
from stui.port.run_port import CommandAckStatus

pytestmark = pytest.mark.unit


@dataclass
class FakeInvoker:
    completed: subprocess.CompletedProcess[str]

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        _ = args
        return self.completed


def test_cli_run_adapter_rejects_empty_args() -> None:
    adapter = CliRunAdapter()

    result = adapter.run("")

    assert result.status == CommandAckStatus.REJECTED
    assert result.message == "error: /run requires arguments"


def test_cli_run_adapter_returns_dispatch_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    _ = monkeypatch
    adapter = CliRunAdapter(
        invoker=FakeInvoker(
            subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=0,
            stdout='{"run_id": "run-1234", "status": "CREATED"}',
            stderr="",
        ))
    )
    result = adapter.run("ant")

    assert result.status == CommandAckStatus.ACCEPTED
    assert result.run_id == "run-1234"
    assert result.message == "[run-dispatch] ant:1234\n  ↳ created"


def test_cli_run_adapter_returns_error_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    _ = monkeypatch
    adapter = CliRunAdapter(
        invoker=FakeInvoker(
            subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=1,
            stdout="",
            stderr="boom",
        ))
    )
    result = adapter.run("ant")

    assert result.status == CommandAckStatus.ERROR
    assert result.message == "error: boom"


def test_cli_run_adapter_sanitizes_skill_not_found_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = monkeypatch
    adapter = CliRunAdapter(
        invoker=FakeInvoker(
            subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=1,
            stdout="",
            stderr=(
                "Traceback (most recent call last):\n"
                '  File "/tmp/x.py", line 1, in <module>\n'
                "FileNotFoundError: Skill not found: source=internal ref=av\n"
            ),
        ))
    )
    result = adapter.run("av")

    assert result.status == CommandAckStatus.ERROR
    assert result.message == "error: agent not found: av"
