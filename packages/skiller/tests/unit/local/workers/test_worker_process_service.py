from __future__ import annotations

import os
import subprocess
import sys

import pytest

from skiller.local.workers.process_service import WorkerProcessService

pytestmark = pytest.mark.unit


def test_start_spawns_worker_start(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, object] = {}

    class _FakeProcess:
        pid = 1234

    def fake_popen(cmd, **kwargs):  # noqa: ANN001
        recorded["cmd"] = cmd
        recorded["kwargs"] = kwargs
        return _FakeProcess()

    monkeypatch.setattr("skiller.local.workers.process_service.subprocess.Popen", fake_popen)

    result = WorkerProcessService().start("run-1")

    assert result.command == "start"
    assert result.pid == 1234
    assert result.run_id == "run-1"
    assert recorded["cmd"] == [
        sys.executable,
        "-m",
        "skiller",
        "worker",
        "start",
        "run-1",
    ]
    assert recorded["kwargs"] == {
        "env": os.environ.copy(),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }


def test_resume_spawns_worker_resume(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, object] = {}

    class _FakeProcess:
        pid = 4321

    def fake_popen(cmd, **kwargs):  # noqa: ANN001
        recorded["cmd"] = cmd
        recorded["kwargs"] = kwargs
        return _FakeProcess()

    monkeypatch.setattr("skiller.local.workers.process_service.subprocess.Popen", fake_popen)

    result = WorkerProcessService().resume("run-9")

    assert result.command == "resume"
    assert result.pid == 4321
    assert result.run_id == "run-9"
    assert recorded["cmd"] == [
        sys.executable,
        "-m",
        "skiller",
        "worker",
        "resume",
        "run-9",
    ]
