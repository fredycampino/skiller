from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from skiller.domain.tool.tool_process_model import (
    ToolProcessHandle,
    ToolProcessOutput,
    ToolProcessRequest,
    ToolProcessWait,
    ToolProcessWaitResult,
    ToolProcessWaitStatus,
)
from skiller.domain.tool.tool_process_port import ToolProcessPort


class DefaultToolProcessRunner(ToolProcessPort):
    def __init__(
        self,
        *,
        terminate_timeout_seconds: float = 2.0,
        poll_interval_seconds: float = 0.1,
    ) -> None:
        self.terminate_timeout_seconds = terminate_timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self._processes: dict[str, _ManagedProcess] = {}

    def popen(self, request: ToolProcessRequest) -> ToolProcessHandle:
        process_id = str(uuid.uuid4())
        stdout_file = tempfile.NamedTemporaryFile(
            mode="w+",
            encoding="utf-8",
            delete=False,
        )
        stderr_file = tempfile.NamedTemporaryFile(
            mode="w+",
            encoding="utf-8",
            delete=False,
        )
        process = subprocess.Popen(  # noqa: S603
            request.command,
            cwd=request.cwd,
            env=self._build_env(request.env),
            stdin=subprocess.PIPE,
            stdout=stdout_file,
            stderr=stderr_file,
            text=True,
            start_new_session=True,
        )
        self._processes[process_id] = _ManagedProcess(
            process=process,
            stdout_file=stdout_file,
            stderr_file=stderr_file,
            stdout_path=Path(stdout_file.name),
            stderr_path=Path(stderr_file.name),
        )
        if request.stdin is not None:
            self.write(
                ToolProcessHandle(id=process_id, pid=process.pid),
                request.stdin,
            )
        elif process.stdin is not None:
            process.stdin.close()
        return ToolProcessHandle(id=process_id, pid=process.pid)

    def write(self, handle: ToolProcessHandle, payload: str) -> None:
        process = self._get_process(handle).process
        if process.stdin is None:
            raise RuntimeError(f"Tool process '{handle.id}' stdin is not available")
        process.stdin.write(payload)
        process.stdin.close()

    def poll(self, handle: ToolProcessHandle) -> int | None:
        return self._get_process(handle).process.poll()

    def read(self, handle: ToolProcessHandle) -> ToolProcessOutput:
        managed = self._get_process(handle)
        process = managed.process
        managed.close_output_files()
        stdout = managed.stdout_path.read_text(encoding="utf-8")
        stderr = managed.stderr_path.read_text(encoding="utf-8")
        self._processes.pop(handle.id, None)
        managed.unlink_output_files()
        return ToolProcessOutput(
            exit_code=int(process.returncode or 0),
            stdout=stdout,
            stderr=stderr,
        )

    def terminate(self, handle: ToolProcessHandle) -> None:
        managed = self._get_process(handle)
        self._terminate_process_group(process=managed.process)
        self._processes.pop(handle.id, None)
        managed.close_output_files()
        managed.unlink_output_files()

    def wait(
        self,
        request: ToolProcessWait,
    ) -> ToolProcessWaitResult:
        started_at = time.monotonic()
        while self.poll(request.handle) is None:
            if self._interrupted(request):
                self.terminate(request.handle)
                return ToolProcessWaitResult(status=ToolProcessWaitStatus.INTERRUPTED)

            if self._timed_out(started_at=started_at, timeout=request.timeout):
                self.terminate(request.handle)
                return ToolProcessWaitResult(status=ToolProcessWaitStatus.TIMEOUT)

            time.sleep(self.poll_interval_seconds)

        return ToolProcessWaitResult(
            status=ToolProcessWaitStatus.COMPLETED,
            output=self.read(request.handle),
        )

    def _interrupted(self, request: ToolProcessWait) -> bool:
        if request.interrupt is None:
            return False
        return request.interrupt.signal.is_interrupted(request.interrupt.run_id)

    def _terminate_process_group(self, *, process: subprocess.Popen[str]) -> None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=self.terminate_timeout_seconds)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()

    def _build_env(self, env: dict[str, str]) -> dict[str, str]:
        merged_env = dict(os.environ)
        merged_env.update(env)
        return merged_env

    def _timed_out(
        self,
        *,
        started_at: float,
        timeout: int | float | None,
    ) -> bool:
        if timeout is None:
            return False
        return time.monotonic() - started_at >= timeout

    def _get_process(self, handle: ToolProcessHandle) -> "_ManagedProcess":
        managed = self._processes.get(handle.id)
        if managed is None:
            raise ValueError(f"Tool process '{handle.id}' is not registered")
        return managed


@dataclass
class _ManagedProcess:
    process: subprocess.Popen[str]
    stdout_file: TextIO
    stderr_file: TextIO
    stdout_path: Path
    stderr_path: Path

    def close_output_files(self) -> None:
        self.stdout_file.close()
        self.stderr_file.close()

    def unlink_output_files(self) -> None:
        self.stdout_path.unlink(missing_ok=True)
        self.stderr_path.unlink(missing_ok=True)
