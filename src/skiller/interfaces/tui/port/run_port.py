from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol


class CommandAckStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ERROR = "error"


@dataclass(frozen=True)
class CommandAck:
    status: CommandAckStatus
    run_id: str | None = None
    message: str = ""


class PollingEventKind(StrEnum):
    LOG = "log"
    STATUS = "status"


@dataclass(frozen=True)
class PollingEvent:
    kind: PollingEventKind
    run_id: str = ""
    status: str = ""
    prompt: str = ""
    text: str = ""
    assistant_text: str = ""
    event_type: str = ""
    skill: str = ""
    step: str = ""
    step_type: str = ""
    turn_id: str = ""
    message_type: str = ""
    tool: str = ""
    tool_call_id: str = ""
    command: str = ""
    parent_sequence: int | None = None
    sequence: int | None = None
    context_ref: str = ""
    output: str = ""
    error: str = ""
    event_id: str | None = None


class ObserverType(StrEnum):
    RUN = "run"


class EventObserver(Protocol):
    type: ObserverType

    def notify(self, events: list[PollingEvent]) -> None: ...


class RunObserver(EventObserver, Protocol):
    type: Literal[ObserverType.RUN]
    run_id: str


class RunPort(Protocol):
    def run(self, raw_args: str) -> CommandAck: ...

    def subscribe(self, observer: RunObserver) -> None: ...

    def unsubscribe(self, observer: RunObserver) -> None: ...
