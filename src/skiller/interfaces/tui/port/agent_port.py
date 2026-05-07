from __future__ import annotations

from typing import Protocol

from skiller.interfaces.tui.port.run_port import CommandAck


class AgentPort(Protocol):
    def interrupt(self, run_id: str) -> CommandAck: ...
