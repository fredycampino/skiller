from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

import pytest

from stui.adapter.events.cli_log_event_adapter import CliLogEventAdapter
from stui.adapter.events.log_event_mapper import LogEventMapper
from stui.port.event_models import (
    AgentAssistantMessagePayload,
    AgentFinalAssistantMessagePayload,
    AgentLifecyclePayload,
    AgentStopReason,
    AgentToolResultPayload,
    AgentToolResultStatus,
    LogEventType,
    RunCreatePayload,
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


def test_cli_log_event_adapter_parses_run_create_payload() -> None:
    event = _mapped_event(
        [
            {
                "sequence": 1,
                "id": "event-1",
                "run_id": "run-1",
                "type": "RUN_CREATE",
                "step_id": None,
                "step_type": None,
                "agent_sequence": None,
                "created_at": "2026-05-12T10:30:15Z",
                "payload": {
                    "ref": "ant",
                    "source": "internal",
                },
            }
        ]
    )

    assert event.event_type == LogEventType.RUN_CREATE
    assert isinstance(event.payload, RunCreatePayload)
    assert event.payload.ref == "ant"
    assert event.payload.source == "internal"


def test_cli_log_event_adapter_parses_step_success_payload() -> None:
    event = _mapped_event(
        [
            {
                "sequence": 10,
                "id": "event-1",
                "run_id": "run-1",
                "type": "STEP_SUCCESS",
                "step_id": "answer",
                "step_type": "agent",
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
    assert event.step_type == "agent"
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


def test_cli_log_event_adapter_parses_agent_assistant_message_total_tokens() -> None:
    event = _mapped_event(
        [
            {
                "sequence": 88,
                "id": "event-88",
                "run_id": "run-1",
                "type": "AGENT_ASSISTANT_MESSAGE",
                "step_id": "support_agent",
                "step_type": "agent",
                "agent_sequence": 16,
                "created_at": "2026-05-12T10:30:18Z",
                "payload": {
                    "text": "summary",
                    "total_tokens": 2144,
                },
            }
        ]
    )

    assert event.event_type == LogEventType.AGENT_ASSISTANT_MESSAGE
    assert isinstance(event.payload, AgentAssistantMessagePayload)
    assert event.payload.text == "summary"
    assert event.payload.total_tokens == 2144


def test_cli_log_event_adapter_parses_agent_final_assistant_message_context() -> None:
    event = _mapped_event(
        [
            {
                "sequence": 89,
                "id": "event-89",
                "run_id": "run-1",
                "type": "AGENT_FINAL_ASSISTANT_MESSAGE",
                "step_id": "support_agent",
                "step_type": "agent",
                "agent_sequence": 17,
                "created_at": "2026-05-12T10:30:20Z",
                "payload": {
                    "text": "Done",
                    "context": {
                        "compaction_enabled": False,
                        "max_window_ratio": 0.8,
                        "max_window_tokens": 1000000,
                        "total_tokens": 2144,
                        "model": "MiniMax-M2.5",
                    },
                },
            }
        ]
    )

    assert event.event_type == LogEventType.AGENT_FINAL_ASSISTANT_MESSAGE
    assert isinstance(event.payload, AgentFinalAssistantMessagePayload)
    assert event.payload.text == "Done"
    assert event.payload.context.total_tokens == 2144
    assert event.payload.context.model == "MiniMax-M2.5"


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
                    "step_type": "agent",
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
