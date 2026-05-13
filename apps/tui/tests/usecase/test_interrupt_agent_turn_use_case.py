from __future__ import annotations

import asyncio

import pytest

from apps.tui.tests.support import FakeAgentPort
from stui.port.run_port import CommandAck, CommandAckStatus
from stui.usecase import (
    interrupt_agent_turn_use_case as interrupt_agent_turn_use_case_module,
)
from stui.usecase.interrupt_agent_turn_use_case import (
    InterruptAgentTurnUseCase,
)
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    ViewStatusKind,
)

pytestmark = pytest.mark.unit


def test_interrupt_agent_turn_use_case_accepts_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return function(*args, **kwargs)

    monkeypatch.setattr(interrupt_agent_turn_use_case_module.asyncio, "to_thread", fake_to_thread)

    async def run() -> None:
        port = FakeAgentPort(
            ack=CommandAck(status=CommandAckStatus.ACCEPTED, message="[agent-interrupt] ok")
        )
        state = ConsoleScreenState(session_key="main")

        result = await InterruptAgentTurnUseCase(agent_port=port).execute(
            state=state,
            run_id="run-1234",
        )

        assert result.state is state
        assert result.interrupted is True
        assert port.called_with == ["run-1234"]
        assert state.transcript.items == []

    asyncio.run(run())


def test_interrupt_agent_turn_use_case_records_error_on_rejected_ack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return function(*args, **kwargs)

    monkeypatch.setattr(interrupt_agent_turn_use_case_module.asyncio, "to_thread", fake_to_thread)

    async def run() -> None:
        port = FakeAgentPort(
            ack=CommandAck(status=CommandAckStatus.ERROR, message="error: interrupt failed")
        )
        state = ConsoleScreenState(session_key="main")

        result = await InterruptAgentTurnUseCase(agent_port=port).execute(
            state=state,
            run_id="run-1234",
        )

        assert result.state is state
        assert result.interrupted is False
        assert port.called_with == ["run-1234"]
        assert isinstance(state.transcript.items[-1], DispatchErrorItem)
        assert state.transcript.items[-1].message == "error: interrupt failed"
        assert state.view_status.kind == ViewStatusKind.ERROR

    asyncio.run(run())
