from __future__ import annotations

from dataclasses import dataclass

from stui.adapter.default_agent_port import DefaultAgentPort
from stui.port.run_port import CommandAck, CommandAckStatus


@dataclass
class FakeAgentAdapter:
    called_with: str | None = None

    def interrupt(self, run_id: str) -> CommandAck:
        self.called_with = run_id
        return CommandAck(
            status=CommandAckStatus.ACCEPTED,
            run_id=run_id,
            message="accepted",
        )


def test_default_agent_port_delegates_to_command_adapter() -> None:
    adapter = FakeAgentAdapter()
    port = DefaultAgentPort(command_adapter=adapter)

    result = port.interrupt("run-1234")

    assert result == CommandAck(
        status=CommandAckStatus.ACCEPTED,
        run_id="run-1234",
        message="accepted",
    )
    assert adapter.called_with == "run-1234"
