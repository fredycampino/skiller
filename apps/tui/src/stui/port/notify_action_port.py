from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class NotifyActionAckStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ERROR = "error"


@dataclass(frozen=True)
class NotifyActionAck:
    status: NotifyActionAckStatus
    run_id: str
    action_uid: str
    message: str = ""


class NotifyActionPort(Protocol):
    def open(self, *, run_id: str, action_uid: str, url: str) -> NotifyActionAck: ...

    def done(self, *, run_id: str, action_uid: str) -> NotifyActionAck: ...
