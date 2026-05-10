from __future__ import annotations

import subprocess
from dataclasses import dataclass

import pytest
from stui.adapter.cli_waiting_adapter import CliWaitingAdapter
from stui.port.run_port import CommandAckStatus

pytestmark = pytest.mark.unit


@dataclass
class FakeInvoker:
    completed: subprocess.CompletedProcess[str]

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        _ = args
        return self.completed


def test_cli_waiting_adapter_rejects_empty_run_id() -> None:
    adapter = CliWaitingAdapter()

    result = adapter.send_input(run_id="", text="hello")

    assert result.status == CommandAckStatus.REJECTED
    assert result.message == "error: run_id is required"


def test_cli_waiting_adapter_rejects_empty_text() -> None:
    adapter = CliWaitingAdapter()

    result = adapter.send_input(run_id="run-1234", text="   ")

    assert result.status == CommandAckStatus.REJECTED
    assert result.message == "error: reply text is required"


def test_cli_waiting_adapter_accepts_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _ = monkeypatch
    adapter = CliWaitingAdapter(
        invoker=FakeInvoker(
            subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=0,
            stdout='{"accepted": true, "matched_runs": ["run-1234"]}',
            stderr="",
        ))
    )
    result = adapter.send_input(run_id="run-1234", text="hello")

    assert result.status == CommandAckStatus.ACCEPTED
    assert result.run_id == "run-1234"


def test_cli_waiting_adapter_maps_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    _ = monkeypatch
    adapter = CliWaitingAdapter(
        invoker=FakeInvoker(
            subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=1,
            stdout='{"accepted": false, "error": "no waiting input"}',
            stderr="",
        ))
    )
    result = adapter.send_input(run_id="run-1234", text="hello")

    assert result.status == CommandAckStatus.REJECTED
    assert result.message == "error: no waiting input"
