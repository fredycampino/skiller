from __future__ import annotations

import os
import signal
import subprocess
from typing import Any

import pytest

from skiller.domain.tool.tool_process_model import (
    ToolProcessInterrupt,
    ToolProcessRequest,
    ToolProcessWait,
    ToolProcessWaitStatus,
)
from skiller.infrastructure.tools.process.default_tool_process import (
    DefaultToolProcessRunner,
)

pytestmark = pytest.mark.unit


def test_popen_starts_process_group_and_returns_handle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, object] = {}
    process = _FakeProcess()
    _patch_popen(monkeypatch=monkeypatch, process=process, recorded=recorded)

    runner = DefaultToolProcessRunner()
    handle = runner.popen(
        ToolProcessRequest(
            command=["/bin/bash", "-lc", "pwd"],
            cwd="/tmp",
            env={"A": "1"},
            stdin="hello",
        )
    )

    assert handle.pid == 1234
    assert handle.id
    assert process.stdin.value == "hello"
    assert process.stdin.closed is True
    assert recorded["cmd"] == ["/bin/bash", "-lc", "pwd"]
    assert recorded["kwargs"] == {
        "cwd": "/tmp",
        "env": {**os.environ, "A": "1"},
        "stdin": subprocess.PIPE,
        "stdout": recorded["kwargs"]["stdout"],
        "stderr": recorded["kwargs"]["stderr"],
        "text": True,
        "start_new_session": True,
    }
    assert recorded["kwargs"]["stdout"].name
    assert recorded["kwargs"]["stderr"].name
    runner.read(handle)


def test_poll_and_read_return_process_output(monkeypatch: pytest.MonkeyPatch) -> None:
    process = _FakeProcess(stdout="ok", stderr="warn", returncode=7)
    _patch_popen(monkeypatch=monkeypatch, process=process)
    runner = DefaultToolProcessRunner()

    handle = runner.popen(ToolProcessRequest(command=["cmd"]))

    assert runner.poll(handle) == 7
    assert runner.read(handle).exit_code == 7
    with pytest.raises(ValueError, match="is not registered"):
        runner.poll(handle)


def test_popen_closes_stdin_when_payload_is_not_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _FakeProcess()
    _patch_popen(monkeypatch=monkeypatch, process=process)
    runner = DefaultToolProcessRunner()

    handle = runner.popen(ToolProcessRequest(command=["cmd"]))

    assert process.stdin.closed is True
    runner.read(handle)


def test_terminate_sends_sigterm_to_process_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _FakeProcess()
    killed: list[tuple[int, signal.Signals]] = []
    _patch_popen(monkeypatch=monkeypatch, process=process)
    monkeypatch.setattr(
        "skiller.infrastructure.tools.process.default_tool_process.os.killpg",
        lambda pid, sig: killed.append((pid, sig)),
    )
    runner = DefaultToolProcessRunner()
    handle = runner.popen(ToolProcessRequest(command=["cmd"]))

    runner.terminate(handle)

    assert killed == [(1234, signal.SIGTERM)]
    assert process.wait_calls == [2.0]
    with pytest.raises(ValueError, match="is not registered"):
        runner.poll(handle)


def test_terminate_escalates_to_sigkill_after_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _FakeProcess(wait_timeout_once=True)
    killed: list[tuple[int, signal.Signals]] = []
    _patch_popen(monkeypatch=monkeypatch, process=process)
    monkeypatch.setattr(
        "skiller.infrastructure.tools.process.default_tool_process.os.killpg",
        lambda pid, sig: killed.append((pid, sig)),
    )
    runner = DefaultToolProcessRunner(terminate_timeout_seconds=0.5)
    handle = runner.popen(ToolProcessRequest(command=["cmd"]))

    runner.terminate(handle)

    assert killed == [(1234, signal.SIGTERM), (1234, signal.SIGKILL)]
    assert process.wait_calls == [0.5, None]


def test_wait_returns_completed_with_output_even_when_exit_code_is_non_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _FakeProcess(stdout="", stderr="boom", returncode=7)
    _patch_popen(monkeypatch=monkeypatch, process=process)
    runner = DefaultToolProcessRunner()
    handle = runner.popen(ToolProcessRequest(command=["cmd"]))

    result = runner.wait(ToolProcessWait(handle=handle))

    assert result.status == ToolProcessWaitStatus.COMPLETED
    assert result.output is not None
    assert result.output.exit_code == 7
    assert result.output.stderr == "boom"


def test_wait_terminates_and_returns_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _FakeProcess(returncode=None)
    killed: list[tuple[int, signal.Signals]] = []
    _patch_popen(monkeypatch=monkeypatch, process=process)
    monkeypatch.setattr(
        "skiller.infrastructure.tools.process.default_tool_process.os.killpg",
        lambda pid, sig: killed.append((pid, sig)),
    )
    timestamps = iter([0.0, 2.0])
    monkeypatch.setattr(
        "skiller.infrastructure.tools.process.default_tool_process.time.monotonic",
        lambda: next(timestamps),
    )
    runner = DefaultToolProcessRunner(poll_interval_seconds=0)
    handle = runner.popen(ToolProcessRequest(command=["cmd"]))

    result = runner.wait(
        ToolProcessWait(
            handle=handle,
            timeout=1,
        )
    )

    assert result.status == ToolProcessWaitStatus.TIMEOUT
    assert result.output is None
    assert killed == [(1234, signal.SIGTERM)]


def test_wait_terminates_and_returns_interrupted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _FakeProcess(returncode=None)
    killed: list[tuple[int, signal.Signals]] = []
    _patch_popen(monkeypatch=monkeypatch, process=process)
    monkeypatch.setattr(
        "skiller.infrastructure.tools.process.default_tool_process.os.killpg",
        lambda pid, sig: killed.append((pid, sig)),
    )
    runner = DefaultToolProcessRunner(poll_interval_seconds=0)
    handle = runner.popen(ToolProcessRequest(command=["cmd"]))

    result = runner.wait(
        ToolProcessWait(
            handle=handle,
            interrupt=ToolProcessInterrupt(
                run_id="run-1",
                signal=_InterruptedSignal(),
            ),
        )
    )

    assert result.status == ToolProcessWaitStatus.INTERRUPTED
    assert result.output is None
    assert killed == [(1234, signal.SIGTERM)]


def _patch_popen(
    *,
    monkeypatch: pytest.MonkeyPatch,
    process: "_FakeProcess",
    recorded: dict[str, object] | None = None,
) -> None:
    def fake_popen(cmd: list[str], **kwargs: Any) -> _FakeProcess:
        if recorded is not None:
            recorded["cmd"] = cmd
            recorded["kwargs"] = kwargs
        kwargs["stdout"].write(process.stdout)
        kwargs["stderr"].write(process.stderr)
        kwargs["stdout"].flush()
        kwargs["stderr"].flush()
        return process

    monkeypatch.setattr(
        "skiller.infrastructure.tools.process.default_tool_process.subprocess.Popen",
        fake_popen,
    )


class _FakeProcess:
    def __init__(
        self,
        *,
        stdout: str = "",
        stderr: str = "",
        returncode: int | None = 0,
        wait_timeout_once: bool = False,
    ) -> None:
        self.pid = 1234
        self.returncode = returncode
        self.stdin = _FakeStdin()
        self.stdout = stdout
        self.stderr = stderr
        self.wait_timeout_once = wait_timeout_once
        self.wait_calls: list[float | None] = []

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls.append(timeout)
        if self.wait_timeout_once:
            self.wait_timeout_once = False
            raise subprocess.TimeoutExpired(cmd=["cmd"], timeout=timeout)
        return self.returncode


class _FakeStdin:
    def __init__(self) -> None:
        self.value = ""
        self.closed = False

    def write(self, payload: str) -> int:
        self.value += payload
        return len(payload)

    def close(self) -> None:
        self.closed = True


class _InterruptedSignal:
    def is_interrupted(self, run_id: str) -> bool:
        _ = run_id
        return True
