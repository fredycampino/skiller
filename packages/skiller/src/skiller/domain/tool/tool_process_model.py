from dataclasses import dataclass, field
from typing import Protocol, TypeAlias


@dataclass(frozen=True)
class ToolProcessRequest:
    command: list[str]
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    stdin: str | None = None
    timeout: int | float | None = None


@dataclass(frozen=True)
class ToolProcessHandle:
    id: str
    pid: int


@dataclass(frozen=True)
class ToolProcessStarted:
    handle: ToolProcessHandle


@dataclass(frozen=True)
class ToolProcessStartFailed:
    error: str


ToolProcessStartResult: TypeAlias = ToolProcessStarted | ToolProcessStartFailed


@dataclass(frozen=True)
class ToolProcessOutput:
    exit_code: int
    stdout: str
    stderr: str


class ToolProcessInterruptSignal(Protocol):
    def is_interrupted(self, run_id: str) -> bool: ...


@dataclass(frozen=True)
class ToolProcessInterrupt:
    run_id: str
    signal: ToolProcessInterruptSignal


@dataclass(frozen=True)
class ToolProcessWait:
    handle: ToolProcessHandle
    timeout: int | float | None = None
    interrupt: ToolProcessInterrupt | None = None


@dataclass(frozen=True)
class ToolProcessCompleted:
    output: ToolProcessOutput


@dataclass(frozen=True)
class ToolProcessTimedOut:
    pass


@dataclass(frozen=True)
class ToolProcessInterrupted:
    pass


@dataclass(frozen=True)
class ToolProcessWaitFailed:
    error: str


ToolProcessWaitResult: TypeAlias = (
    ToolProcessCompleted
    | ToolProcessTimedOut
    | ToolProcessInterrupted
    | ToolProcessWaitFailed
)
