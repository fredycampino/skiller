from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from skiller.domain.event.event_model import RuntimeEvent
from skiller.domain.run.run_model import RunStatus

DEFAULT_OBSERVE_TAIL = 100
MAX_OBSERVE_TAIL = 1000
DEFAULT_OBSERVE_BATCH_SIZE = 100


class ObserveFrameKind(StrEnum):
    START = "start"
    EVENT = "event"
    WAIT = "wait"
    STOP = "stop"


class ObserveWaitType(StrEnum):
    INPUT = "input"
    WEBHOOK = "webhook"


@dataclass(frozen=True, kw_only=True)
class ObserveRunSettings:
    default_tail: int = DEFAULT_OBSERVE_TAIL
    max_tail: int = MAX_OBSERVE_TAIL
    batch_size: int = DEFAULT_OBSERVE_BATCH_SIZE


@dataclass(frozen=True, kw_only=True)
class ObserveRunInput:
    run_id: str
    after: int | None
    tail: int


@dataclass(frozen=True, kw_only=True)
class ObserveStart:
    run_id: str
    requested_after: int | None
    effective_after: int
    last_sequence: int
    tail: int
    truncated: bool


@dataclass(frozen=True, kw_only=True)
class ObserveEvent:
    event: RuntimeEvent


@dataclass(frozen=True, kw_only=True)
class ObserveWait:
    sequence: int
    wait_type: ObserveWaitType
    prompt: str = ""


@dataclass(frozen=True)
class ObserveIdle:
    pass


@dataclass(frozen=True, kw_only=True)
class ObserveStop:
    sequence: int
    status: RunStatus


ObserveRunResult: TypeAlias = ObserveStart | ObserveEvent | ObserveWait | ObserveIdle | ObserveStop
