from __future__ import annotations

import subprocess
from dataclasses import dataclass

import pytest

from stui.adapter.cli_run_adapter import CliRunAdapter
from stui.port.run_port import (
    RunDispatchErrorKind,
    RunRuntimeStatusKind,
    RunRuntimeWaitType,
)

pytestmark = pytest.mark.unit


@dataclass
class FakeInvoker:
    completed: subprocess.CompletedProcess[str]
    calls: list[tuple[str, ...]]

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        return self.completed


def _invoker(
    *,
    returncode: int = 0,
    stdout: str = '{"run_id": "run-1234", "status": "CREATED", "worker_pid": 3}',
    stderr: str = "",
) -> FakeInvoker:
    return FakeInvoker(
        calls=[],
        completed=subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        ),
    )


def test_cli_run_adapter_rejects_empty_args() -> None:
    adapter = CliRunAdapter()

    result = adapter.run("")

    assert result.error.kind == RunDispatchErrorKind.INVALID_ARGS
    assert result.error.message == "/run requires arguments"


def test_cli_run_adapter_returns_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    _ = monkeypatch
    invoker = _invoker()
    adapter = CliRunAdapter(invoker=invoker)

    result = adapter.run("ant")

    assert result.run_id == "run-1234"
    assert result.status == RunRuntimeStatusKind.CREATED
    assert result.worker_pid == 3
    assert invoker.calls == [("run", "ant", "--detach")]


def test_cli_run_adapter_runs_yaml_path_as_external_skill_file() -> None:
    invoker = _invoker()
    adapter = CliRunAdapter(invoker=invoker)

    result = adapter.run("/virtual/notify_cli_e2e.yaml")

    assert result.error.kind == RunDispatchErrorKind.NONE
    assert invoker.calls == [
        (
            "run",
            "--file",
            "/virtual/notify_cli_e2e.yaml",
            "--detach",
        )
    ]


def test_cli_run_adapter_returns_runtime_status(monkeypatch: pytest.MonkeyPatch) -> None:
    _ = monkeypatch
    adapter = CliRunAdapter(
        invoker=_invoker(
            stdout=(
                '{"status": "WAITING", "wait_type": "input", '
                '"prompt": "Write a message", '
                '"last_event_sequence": "42", "last_event_type": "RUN_WAITING"}'
            ),
        )
    )

    result = adapter.status("run-1234")

    assert result.run_id == "run-1234"
    assert result.status == RunRuntimeStatusKind.WAITING
    assert result.wait_type == RunRuntimeWaitType.INPUT
    assert result.prompt == "Write a message"
    assert result.last_event_sequence == 42
    assert result.last_event_type == "RUN_WAITING"


def test_cli_run_adapter_returns_none_when_status_command_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = monkeypatch
    adapter = CliRunAdapter(invoker=_invoker(returncode=1, stdout="", stderr="boom"))

    result = adapter.status("run-1234")

    assert result is None


def test_cli_run_adapter_returns_none_when_status_payload_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = monkeypatch
    adapter = CliRunAdapter(invoker=_invoker(stdout="not-json"))

    result = adapter.status("run-1234")

    assert result is None


def test_cli_run_adapter_returns_none_when_status_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = monkeypatch
    adapter = CliRunAdapter(invoker=_invoker(stdout='{"status": "BOGUS"}'))

    result = adapter.status("run-1234")

    assert result is None


def test_cli_run_adapter_rejects_non_json_runtime_error() -> None:
    adapter = CliRunAdapter(invoker=_invoker(returncode=1, stdout="", stderr="boom"))

    result = adapter.run("ant")

    assert result.error.kind == RunDispatchErrorKind.RUNTIME_ERROR
    assert result.error.message == "runtime command returned invalid JSON"


@pytest.mark.parametrize(
    ("code", "kind"),
    [
        ("RUN_ARGUMENT_INVALID", RunDispatchErrorKind.INVALID_ARGS),
        ("FLOW_NOT_FOUND", RunDispatchErrorKind.FLOW_NOT_FOUND),
        ("WEBHOOK_WAIT_CONFLICT", RunDispatchErrorKind.WEBHOOK_WAIT_CONFLICT),
        ("WORKER_START_FAILED", RunDispatchErrorKind.WORKER_START_FAILED),
        ("RUNTIME_INITIALIZATION_FAILED", RunDispatchErrorKind.INITIALIZATION_FAILED),
        ("RUN_CREATE_FAILED", RunDispatchErrorKind.CREATE_FAILED),
    ],
)
def test_cli_run_adapter_maps_normalized_runtime_errors(
    code: str,
    kind: RunDispatchErrorKind,
) -> None:
    adapter = CliRunAdapter(
        invoker=_invoker(
            returncode=1,
            stdout=f'{{"error": {{"code": "{code}", "message": "failure"}}}}',
        )
    )

    result = adapter.run("ant")

    assert result.error.kind == kind
    assert result.error.message == "failure"


def test_cli_run_adapter_preserves_webhook_conflict_message() -> None:
    message = (
        "Webhook 'github:42' is already being waited by run 'existing'. "
        "Delete it with 'skiller delete existing' or wait for it to finish."
    )
    adapter = CliRunAdapter(
        invoker=_invoker(
            returncode=1,
            stdout=f'{{"error": {{"code": "WEBHOOK_WAIT_CONFLICT", "message": "{message}"}}}}',
        )
    )

    result = adapter.run("deploy --arg pr=42")

    assert result.error.kind == RunDispatchErrorKind.WEBHOOK_WAIT_CONFLICT
    assert result.error.message == message
