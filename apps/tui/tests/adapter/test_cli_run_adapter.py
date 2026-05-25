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
    adapter = CliRunAdapter(
        invoker=_invoker(returncode=1, stdout="", stderr="boom")
    )

    result = adapter.status("run-1234")

    assert result is None


def test_cli_run_adapter_returns_none_when_status_payload_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = monkeypatch
    adapter = CliRunAdapter(
        invoker=_invoker(stdout="not-json")
    )

    result = adapter.status("run-1234")

    assert result is None


def test_cli_run_adapter_returns_none_when_status_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = monkeypatch
    adapter = CliRunAdapter(
        invoker=_invoker(stdout='{"status": "BOGUS"}')
    )

    result = adapter.status("run-1234")

    assert result is None


def test_cli_run_adapter_returns_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _ = monkeypatch
    adapter = CliRunAdapter(
        invoker=_invoker(returncode=1, stdout="", stderr="boom")
    )

    result = adapter.run("ant")

    assert result.error.kind == RunDispatchErrorKind.RUNTIME_ERROR
    assert result.error.message == "boom"


def test_cli_run_adapter_returns_dispatch_error_when_skill_is_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = monkeypatch
    adapter = CliRunAdapter(
        invoker=_invoker(
            returncode=1,
            stdout="",
            stderr=(
                "Traceback (most recent call last):\n"
                '  File "/tmp/x.py", line 1, in <module>\n'
                "FileNotFoundError: Skill not found: source=internal ref=av\n"
            ),
        )
    )
    result = adapter.run("av")

    assert result.error.kind == RunDispatchErrorKind.RUN_NOT_FOUND
    assert result.error.message == "agent not found: av"


def test_cli_run_adapter_returns_run_not_found_when_skill_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = monkeypatch
    adapter = CliRunAdapter(
        invoker=_invoker(
            returncode=1,
            stdout="",
            stderr="Invalid skill format for 'broken'. Skill requires non-empty root 'start'",
        )
    )

    result = adapter.run("broken")

    assert result.error.kind == RunDispatchErrorKind.RUN_NOT_FOUND
    assert (
        result.error.message
        == "Invalid skill format for 'broken'. Skill requires non-empty root 'start'"
    )


def test_cli_run_adapter_returns_invalid_args_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _ = monkeypatch
    adapter = CliRunAdapter(
        invoker=_invoker(
            returncode=1,
            stdout="",
            stderr="Invalid --arg 'foo'. Expected key=value.",
        )
    )

    result = adapter.run("ant --arg foo")

    assert result.error.kind == RunDispatchErrorKind.INVALID_ARGS
    assert result.error.message == "Invalid --arg 'foo'. Expected key=value."


def test_cli_run_adapter_returns_worker_start_failed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = monkeypatch
    adapter = CliRunAdapter(
        invoker=_invoker(
            returncode=1,
            stdout="",
            stderr="worker process did not start",
        )
    )

    result = adapter.run("ant")

    assert result.error.kind == RunDispatchErrorKind.WORKER_START_FAILED
    assert result.error.message == "worker process did not start"
