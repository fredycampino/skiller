from __future__ import annotations

import subprocess
from dataclasses import dataclass

import pytest

from stui.adapter.cli_notify_action_adapter import CliNotifyActionAdapter
from stui.port.notify_action_port import NotifyActionAckStatus

pytestmark = pytest.mark.unit


@dataclass
class FakeInvoker:
    completed: subprocess.CompletedProcess[str]

    def __post_init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        return self.completed


def test_cli_notify_action_adapter_rejects_empty_run_id() -> None:
    adapter = CliNotifyActionAdapter()

    result = adapter.done(run_id="", step_id="auth_link")

    assert result.status == NotifyActionAckStatus.REJECTED
    assert result.message == "error: run_id is required"


def test_cli_notify_action_adapter_rejects_empty_step_id() -> None:
    adapter = CliNotifyActionAdapter()

    result = adapter.done(run_id="run-1", step_id="   ")

    assert result.status == NotifyActionAckStatus.REJECTED
    assert result.message == "error: step_id is required"


def test_cli_notify_action_adapter_accepts_done_response() -> None:
    invoker = FakeInvoker(
        subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=0,
            stdout=(
                '{"run_id": "run-1", "step_id": "auth_link", '
                '"status": "DONE", "done": true, "changed": true}'
            ),
            stderr="",
        )
    )
    adapter = CliNotifyActionAdapter(invoker=invoker)

    result = adapter.done(run_id="run-1", step_id="auth_link")

    assert result.status == NotifyActionAckStatus.ACCEPTED
    assert result.run_id == "run-1"
    assert result.step_id == "auth_link"
    assert invoker.calls == [("action", "done", "run-1", "auth_link")]


def test_cli_notify_action_adapter_maps_rejected_response() -> None:
    invoker = FakeInvoker(
        subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=1,
            stdout=(
                '{"run_id": "run-1", "step_id": "auth_link", '
                '"status": "STEP_NOT_FOUND", "done": false, '
                '"changed": false, "error": "step not found"}'
            ),
            stderr="",
        )
    )
    adapter = CliNotifyActionAdapter(invoker=invoker)

    result = adapter.done(run_id="run-1", step_id="auth_link")

    assert result.status == NotifyActionAckStatus.REJECTED
    assert result.message == "error: step not found"


def test_cli_notify_action_adapter_maps_invalid_json() -> None:
    invoker = FakeInvoker(
        subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=1,
            stdout="not-json",
            stderr="",
        )
    )
    adapter = CliNotifyActionAdapter(invoker=invoker)

    result = adapter.done(run_id="run-1", step_id="auth_link")

    assert result.status == NotifyActionAckStatus.ERROR
    assert result.message == "error: not-json"
