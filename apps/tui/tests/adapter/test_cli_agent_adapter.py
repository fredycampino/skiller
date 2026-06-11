from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

import pytest

from stui.adapter.cli_agent_adapter import CliAgentAdapter
from stui.port.agent_port import AgentStatsStatus
from stui.port.run_port import CommandAckStatus

pytestmark = pytest.mark.unit


@dataclass
class FakeInvoker:
    completed: subprocess.CompletedProcess[str]
    calls: list[tuple[str, ...]] = field(default_factory=list)

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        return self.completed


def test_cli_agent_adapter_requires_run_id() -> None:
    adapter = CliAgentAdapter()

    with pytest.raises(RuntimeError, match="agent interrupt command requires run_id"):
        adapter.interrupt("")


def test_cli_agent_adapter_accepts_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    _ = monkeypatch
    adapter = CliAgentAdapter(
        invoker=FakeInvoker(
            subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=0,
            stdout='{"run_id":"run-1234","status":"ENQUEUED","enqueued":true}',
            stderr="",
        ))
    )
    result = adapter.interrupt("run-1234")

    assert result.status == CommandAckStatus.ACCEPTED
    assert result.run_id == "run-1234"
    assert result.message == "[agent-interrupt] run-1234\n  ↳ enqueued"


def test_cli_agent_adapter_maps_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _ = monkeypatch
    adapter = CliAgentAdapter(
        invoker=FakeInvoker(
            subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=1,
            stdout=(
                '{"run_id":"run-1234","status":"RUN_NOT_FOUND",'
                '"enqueued":false,"error":"run not found"}'
            ),
            stderr="",
        ))
    )
    result = adapter.interrupt("run-1234")

    assert result.status == CommandAckStatus.ERROR
    assert result.run_id == "run-1234"
    assert result.message == "error: run not found"


def test_cli_agent_adapter_maps_not_running_interrupt() -> None:
    adapter = CliAgentAdapter(
        invoker=FakeInvoker(
            subprocess.CompletedProcess(
                args=["python", "-m", "skiller"],
                returncode=1,
                stdout=(
                    '{"run_id":"run-1234","status":"NOT_RUNNING",'
                    '"enqueued":false,"error":"run is not running"}'
                ),
                stderr="",
            )
        )
    )

    result = adapter.interrupt("run-1234")

    assert result.status == CommandAckStatus.ERROR
    assert result.run_id == "run-1234"
    assert result.message == "error: run is not running"


def test_cli_agent_adapter_reads_agent_stats() -> None:
    invoker = FakeInvoker(
        subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=0,
            stdout="""
            {
              "run_id": "run-1234",
              "agent_id": "support_agent",
              "status": "OK",
              "ok": true,
              "context_id": "ctx-1234",
              "context": {
                "entries": 24,
                "estimated_tokens": 2618,
                "window": {
                  "start_sequence": 1,
                  "end_sequence": 24,
                  "current_tokens": 2618,
                  "limit_tokens": 80000,
                  "capacity_tokens": 100000
                }
              }
            }
            """,
            stderr="",
        )
    )
    adapter = CliAgentAdapter(invoker=invoker)

    result = adapter.stats(run_id="run-1234", agent_id="support_agent")

    assert invoker.calls == [
        ("agent", "stats", "run-1234", "--agent", "support_agent")
    ]
    assert result.status == AgentStatsStatus.OK
    assert result.run_id == "run-1234"
    assert result.agent_id == "support_agent"
    assert result.context_id == "ctx-1234"
    assert result.context is not None
    assert result.context.entries == 24
    assert result.context.estimated_tokens == 2618
    assert result.context.window.current_tokens == 2618
    assert result.context.window.limit_tokens == 80000
    assert result.context.window.capacity_tokens == 100000


def test_cli_agent_adapter_maps_agent_stats_error() -> None:
    adapter = CliAgentAdapter(
        invoker=FakeInvoker(
            subprocess.CompletedProcess(
                args=["python", "-m", "skiller"],
                returncode=1,
                stdout="""
                {
                  "run_id": "run-1234",
                  "agent_id": "support_agent",
                  "status": "AGENT_CONTEXT_NOT_READY",
                  "ok": false,
                  "error": "Agent 'support_agent' has no attached context"
                }
                """,
                stderr="",
            )
        )
    )

    result = adapter.stats(run_id="run-1234", agent_id="support_agent")

    assert result.status == AgentStatsStatus.AGENT_CONTEXT_NOT_READY
    assert result.run_id == "run-1234"
    assert result.agent_id == "support_agent"
    assert result.error == "Agent 'support_agent' has no attached context"
