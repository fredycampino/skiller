from __future__ import annotations

import subprocess
from dataclasses import dataclass

import pytest

from stui.adapter.cli_runs_adapter import CliRunsAdapter
from stui.port.runs_port import RunsPortItem

pytestmark = pytest.mark.unit


@dataclass
class FakeInvoker:
    completed: subprocess.CompletedProcess[str]
    called_with: tuple[str, ...] | None = None

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        self.called_with = args
        return self.completed


def test_cli_runs_adapter_passes_limit_and_status_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    _ = monkeypatch
    invoker = FakeInvoker(
        subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=0,
            stdout='[{"id": "run-1", "status": "WAITING"}]',
            stderr="",
        )
    )
    adapter = CliRunsAdapter(invoker=invoker)
    result = adapter.list_runs(limit=5, statuses=["waiting", "failed"])

    assert result == [
        RunsPortItem(
            id="run-1",
            skill_source="",
            skill_ref="",
            status="WAITING",
            current=None,
            created_at="",
            updated_at="",
        )
    ]
    assert list(invoker.called_with or ()) == [
        "runs",
        "--limit",
        "5",
        "--status",
        "waiting",
        "--status",
        "failed",
    ]


def test_cli_runs_adapter_rejects_invalid_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    _ = monkeypatch
    adapter = CliRunsAdapter(
        invoker=FakeInvoker(
            subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=0,
            stdout='{"id": "run-1"}',
            stderr="",
        ))
    )

    with pytest.raises(RuntimeError, match="runs command returned invalid payload"):
        adapter.list_runs()
