from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class CommandAckStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ERROR = "error"


class RunRuntimeStatusKind(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    WAITING = "waiting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunRuntimeWaitType(StrEnum):
    NONE = "none"
    INPUT = "input"
    WEBHOOK = "webhook"
    CHANNEL = "channel"


class RunDispatchErrorKind(StrEnum):
    NONE = "none"
    RUN_NOT_FOUND = "run_not_found"
    INVALID_ARGS = "invalid_args"
    WORKER_START_FAILED = "worker_start_failed"
    RUNTIME_ERROR = "runtime_error"


@dataclass(frozen=True)
class CommandAck:
    status: CommandAckStatus
    run_id: str | None = None
    message: str = ""


@dataclass(frozen=True)
class RunDispatchError:
    kind: RunDispatchErrorKind
    message: str

    def __bool__(self) -> bool:
        return self.kind != RunDispatchErrorKind.NONE


@dataclass(frozen=True)
class RunDispatch:
    run_id: str
    status: RunRuntimeStatusKind
    worker_pid: int
    error: RunDispatchError


@dataclass(frozen=True)
class RunRuntimeStatus:
    run_id: str
    status: RunRuntimeStatusKind
    wait_type: RunRuntimeWaitType = RunRuntimeWaitType.NONE
    prompt: str = ""
    last_event_sequence: int | None = None
    last_event_type: str = ""


class RunPort(Protocol):
    def run(self, raw_args: str) -> RunDispatch: ...

    def status(self, run_id: str) -> RunRuntimeStatus | None: ...
