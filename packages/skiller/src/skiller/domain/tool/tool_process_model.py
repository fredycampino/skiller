from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


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


class ToolProcessWaitStatus(str, Enum):
    COMPLETED = "COMPLETED"
    TIMEOUT = "TIMEOUT"
    INTERRUPTED = "INTERRUPTED"


@dataclass(frozen=True)
class ToolProcessWaitResult:
    status: ToolProcessWaitStatus
    output: ToolProcessOutput | None = None
