from __future__ import annotations

import asyncio
from dataclasses import dataclass

from skiller.interfaces.tui.port.agent_port import AgentPort
from skiller.interfaces.tui.port.run_port import CommandAckStatus
from skiller.interfaces.tui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    ViewStatusKind,
)


@dataclass(frozen=True)
class InterruptAgentTurnResult:
    state: ConsoleScreenState
    interrupted: bool


@dataclass(frozen=True)
class InterruptAgentTurnUseCase:
    agent_port: AgentPort

    async def execute(
        self,
        *,
        state: ConsoleScreenState,
        run_id: str,
    ) -> InterruptAgentTurnResult:
        normalized_run_id = run_id.strip()
        if not normalized_run_id:
            return InterruptAgentTurnResult(state=state, interrupted=False)

        ack = await asyncio.to_thread(
            self.agent_port.interrupt,
            normalized_run_id,
        )
        if ack.status == CommandAckStatus.ACCEPTED:
            return InterruptAgentTurnResult(state=state, interrupted=True)

        state.transcript.items.append(
            DispatchErrorItem(
                message=ack.message or "error: agent interrupt rejected"
            )
        )
        state.view_status.kind = ViewStatusKind.ERROR
        state.view_status.message = "Error"
        return InterruptAgentTurnResult(state=state, interrupted=False)
