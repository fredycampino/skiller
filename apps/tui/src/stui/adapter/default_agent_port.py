from __future__ import annotations

from dataclasses import dataclass, field

from stui.adapter.cli_agent_adapter import CliAgentAdapter
from stui.port.run_port import CommandAck


@dataclass
class DefaultAgentPort:
    command_adapter: CliAgentAdapter = field(default_factory=CliAgentAdapter)

    def interrupt(self, run_id: str) -> CommandAck:
        return self.command_adapter.interrupt(run_id)
