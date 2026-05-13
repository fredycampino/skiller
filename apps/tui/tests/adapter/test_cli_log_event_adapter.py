from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

import pytest

from stui.adapter.events.cli_log_event_adapter import CliLogEventAdapter
from stui.adapter.events.log_event_mapper import LogEventMapper
from stui.port.event_models import (
    AgentLifecyclePayload,
    AgentStopReason,
    AgentToolResultPayload,
    AgentToolResultStatus,
    LogEventType,
    StepSuccessPayload,
)

pytestmark = pytest.mark.unit


@dataclass
class FakeInvoker:
    completed: subprocess.CompletedProcess[str]
    called_with: tuple[str, ...] | None = None

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        self.called_with = args
        return self.completed


def test_cli_log_event_adapter_passes_cursor_and_limit() -> None:
    invoker = FakeInvoker(_completed([]))
    adapter = CliLogEventAdapter(invoker=invoker)

    result = adapter.list("run-1", after_sequence=42, limit=100)

    assert result == []
    assert list(invoker.called_with or ()) == [
        "logs",
        "run-1",
        "--after",
        "42",
        "--limit",
        "100",
    ]


def test_cli_log_event_adapter_parses_step_success_payload() -> None:
    event = _mapped_event(
        [
            {
                "sequence": 10,
                "id": "event-1",
                "run_id": "run-1",
                "type": "STEP_SUCCESS",
                "step_id": "answer",
                "step_type": "llm_prompt",
                "agent_sequence": None,
                "created_at": "2026-05-12T10:30:15Z",
                "payload": {
                    "output": {
                        "text": "hello",
                        "text_ref": "data.reply",
                        "value": {"data": {"reply": "hello"}},
                        "body_ref": None,
                    },
                    "next": "ask_user",
                },
            }
        ]
    )

    assert event.sequence == 10
    assert event.event_type == LogEventType.STEP_SUCCESS
    assert event.step_id == "answer"
    assert event.step_type == "llm_prompt"
    assert isinstance(event.payload, StepSuccessPayload)
    assert event.payload.output.text == "hello"
    assert event.payload.output.text_ref == "data.reply"
    assert event.payload.output.value == {"data": {"reply": "hello"}}
    assert event.payload.next_step_id == "ask_user"


def test_cli_log_event_adapter_parses_agent_tool_result_payload() -> None:
    event = _mapped_event(
        [
            {
                "sequence": 11,
                "id": "event-2",
                "run_id": "run-1",
                "type": "AGENT_TOOL_RESULT",
                "step_id": "support_agent",
                "step_type": "agent",
                "agent_sequence": 34,
                "created_at": "2026-05-12T10:30:17Z",
                "payload": {
                    "type": "tool_result",
                    "turn_id": "turn-1",
                    "parent_sequence": 32,
                    "tool_call_id": "call-1",
                    "tool": "shell",
                    "status": "COMPLETED",
                    "data": {"ok": True, "exit_code": 0},
                    "text": "ok",
                    "error": None,
                },
            }
        ]
    )

    assert event.event_type == LogEventType.AGENT_TOOL_RESULT
    assert event.agent_sequence == 34
    assert isinstance(event.payload, AgentToolResultPayload)
    assert event.payload.status == AgentToolResultStatus.COMPLETED
    assert event.payload.data == {"ok": True, "exit_code": 0}
    assert event.payload.text == "ok"


def test_cli_log_event_adapter_parses_agent_lifecycle_payload() -> None:
    event = _mapped_event(
        [
            {
                "sequence": 12,
                "id": "event-3",
                "run_id": "run-1",
                "type": "AGENT_INTERRUPTED",
                "step_id": "support_agent",
                "step_type": "agent",
                "agent_sequence": None,
                "created_at": "2026-05-12T10:30:18Z",
                "payload": {
                    "turn_id": "turn-1",
                    "stop_reason": "interrupted",
                },
            }
        ]
    )

    assert isinstance(event.payload, AgentLifecyclePayload)
    assert event.payload.turn_id == "turn-1"
    assert event.payload.stop_reason == AgentStopReason.INTERRUPTED


def test_cli_log_event_adapter_rejects_invalid_payload() -> None:
    with pytest.raises(RuntimeError, match="invalid payload"):
        _mapped_event(
            [
                {
                    "sequence": 10,
                    "id": "event-1",
                    "run_id": "run-1",
                    "type": "STEP_SUCCESS",
                    "step_id": "answer",
                    "step_type": "llm_prompt",
                    "agent_sequence": None,
                    "created_at": "2026-05-12T10:30:15Z",
                    "payload": {},
                }
            ]
        )


def _completed(payload: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["python", "-m", "skiller"],
        returncode=0,
        stdout=json.dumps(payload),
        stderr="",
    )


def _mapped_event(payload: object):
    events = CliLogEventAdapter(invoker=FakeInvoker(_completed(payload))).list("run-1")
    return LogEventMapper().map(events[0])
