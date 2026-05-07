from __future__ import annotations

import subprocess
from dataclasses import dataclass

import pytest

from skiller.interfaces.tui.adapter.cli_agent_adapter import CliAgentAdapter
from skiller.interfaces.tui.port.run_port import CommandAckStatus

pytestmark = pytest.mark.unit


@dataclass
class FakeInvoker:
    completed: subprocess.CompletedProcess[str]

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        _ = args
        return self.completed


def test_cli_agent_adapter_rejects_empty_run_id() -> None:
    adapter = CliAgentAdapter()

    result = adapter.interrupt("")

    assert result.status == CommandAckStatus.REJECTED
    assert result.message == "error: run_id is required"


def test_cli_agent_adapter_accepts_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    _ = monkeypatch
    adapter = CliAgentAdapter(
        invoker=FakeInvoker(
            subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=0,
            stdout='{"run_id":"run-1234","status":"ENQUEUED","enqueued":true}',
            stderr="",
        ))
    )
    result = adapter.interrupt("run-1234")

    assert result.status == CommandAckStatus.ACCEPTED
    assert result.run_id == "run-1234"
    assert result.message == "[agent-interrupt] run-1234\n  ↳ enqueued"


def test_cli_agent_adapter_maps_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _ = monkeypatch
    adapter = CliAgentAdapter(
        invoker=FakeInvoker(
            subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=1,
            stdout='{"error":"run not found"}',
            stderr="",
        ))
    )
    result = adapter.interrupt("run-1234")

    assert result.status == CommandAckStatus.ERROR
    assert result.run_id == "run-1234"
    assert result.message == "error: run not found"
