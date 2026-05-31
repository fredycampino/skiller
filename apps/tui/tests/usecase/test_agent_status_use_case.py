from __future__ import annotations

import pytest

from stui.port.event_models import LogEvent, LogEventType, StepStartedPayload
from stui.usecase.agent_status_use_case import AgentStatusUseCase
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus

pytestmark = pytest.mark.unit


def test_agent_status_updates_agent_id_from_latest_agent_event() -> None:
    context = _context()

    AgentStatusUseCase().execute(
        context=context,
        events=[
            _event(
                sequence=1,
                step_id="first_agent",
                step_type="agent",
            ),
            _event(
                sequence=2,
                step_id="support_agent",
                step_type="agent",
            ),
        ],
    )

    assert context.agent_id == "support_agent"


def test_agent_status_ignores_non_agent_events() -> None:
    context = _context()
    context.agent_id = "support_agent"

    AgentStatusUseCase().execute(
        context=context,
        events=[
            _event(
                sequence=1,
                step_id="show_message",
                step_type="notify",
            )
        ],
    )

    assert context.agent_id == "support_agent"


def _context() -> RunEventContext:
    return RunEventContext(
        run_id="run-1234",
        run_name="demo",
        mode=RunMode.CHAT,
        status=RunStatus.RUNNING,
    )


def _event(
    *,
    sequence: int,
    step_id: str,
    step_type: str,
) -> LogEvent:
    return LogEvent(
        sequence=sequence,
        event_id=f"evt-{sequence}",
        run_id="run-1234",
        event_type=LogEventType.STEP_STARTED,
        step_id=step_id,
        step_type=step_type,
        agent_sequence=None,
        created_at="2026-05-12T10:30:15Z",
        payload=StepStartedPayload(),
    )
