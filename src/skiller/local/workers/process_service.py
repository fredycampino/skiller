from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerProcessStartResult:
    command: str
    pid: int | None
    run_id: str


class WorkerProcessService:
    def start(self, run_id: str) -> WorkerProcessStartResult:
        return self._spawn("start", run_id)

    def run(self, run_id: str) -> WorkerProcessStartResult:
        return self._spawn("run", run_id)

    def resume(self, run_id: str) -> WorkerProcessStartResult:
        return self._spawn("resume", run_id)

    def _spawn(self, command: str, run_id: str) -> WorkerProcessStartResult:
        process = subprocess.Popen(  # noqa: S603
            [sys.executable, "-m", "skiller", "worker", command, run_id],
            env=os.environ.copy(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return WorkerProcessStartResult(
            command=command,
            pid=process.pid,
            run_id=run_id,
        )
