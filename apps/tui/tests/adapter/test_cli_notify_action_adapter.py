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

    result = adapter.done(run_id="", action_uid="action-1")

    assert result.status == NotifyActionAckStatus.REJECTED
    assert result.message == "error: run_id is required"


def test_cli_notify_action_adapter_rejects_empty_action_uid() -> None:
    adapter = CliNotifyActionAdapter()

    result = adapter.done(run_id="run-1", action_uid="   ")

    assert result.status == NotifyActionAckStatus.REJECTED
    assert result.message == "error: action_uid is required"


def test_cli_notify_action_adapter_accepts_done_response() -> None:
    invoker = FakeInvoker(
        subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=0,
            stdout=(
                '{"run_id": "run-1", "action_uid": "action-1", '
                '"status": "DONE", "done": true, "changed": true}'
            ),
            stderr="",
        )
    )
    adapter = CliNotifyActionAdapter(invoker=invoker)

    result = adapter.done(run_id="run-1", action_uid="action-1")

    assert result.status == NotifyActionAckStatus.ACCEPTED
    assert result.run_id == "run-1"
    assert result.action_uid == "action-1"
    assert invoker.calls == [("action", "done", "run-1", "action-1")]


def test_cli_notify_action_adapter_maps_rejected_response() -> None:
    invoker = FakeInvoker(
        subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=1,
            stdout=(
                '{"run_id": "run-1", "action_uid": "action-1", '
                '"status": "ACTION_NOT_FOUND", "done": false, '
                '"changed": false, "error": "action not found"}'
            ),
            stderr="",
        )
    )
    adapter = CliNotifyActionAdapter(invoker=invoker)

    result = adapter.done(run_id="run-1", action_uid="action-1")

    assert result.status == NotifyActionAckStatus.REJECTED
    assert result.message == "error: action not found"


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

    result = adapter.done(run_id="run-1", action_uid="action-1")

    assert result.status == NotifyActionAckStatus.ERROR
    assert result.message == "error: not-json"
