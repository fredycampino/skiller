from __future__ import annotations

from typing import Protocol

from stui.port.run_port import CommandAck


class WaitingPort(Protocol):
    def send_input(self, *, run_id: str, text: str) -> CommandAck: ...
