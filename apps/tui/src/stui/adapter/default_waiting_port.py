from __future__ import annotations

from dataclasses import dataclass, field

from stui.adapter.cli_waiting_adapter import CliWaitingAdapter
from stui.port.waiting_port import WaitingInputAck


@dataclass
class DefaultWaitingPort:
    command_adapter: CliWaitingAdapter = field(default_factory=CliWaitingAdapter)

    def send_input(self, *, run_id: str, text: str) -> WaitingInputAck:
        return self.command_adapter.send_input(run_id=run_id, text=text)
