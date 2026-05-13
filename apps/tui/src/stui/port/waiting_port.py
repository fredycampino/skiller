from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class WaitingInputStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ERROR = "error"


@dataclass(frozen=True)
class WaitingInputAck:
    status: WaitingInputStatus
    run_id: str
    message: str


class WaitingPort(Protocol):
    def send_input(self, *, run_id: str, text: str) -> WaitingInputAck: ...
