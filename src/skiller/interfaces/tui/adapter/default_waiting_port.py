from __future__ import annotations

from dataclasses import dataclass, field

from skiller.interfaces.tui.adapter.cli_waiting_adapter import CliWaitingAdapter
from skiller.interfaces.tui.port.run_port import CommandAck


@dataclass
class DefaultWaitingPort:
    command_adapter: CliWaitingAdapter = field(default_factory=CliWaitingAdapter)

    def send_input(self, *, run_id: str, text: str) -> CommandAck:
        return self.command_adapter.send_input(run_id=run_id, text=text)
