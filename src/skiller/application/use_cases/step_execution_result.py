from dataclasses import dataclass
from enum import Enum


class StepExecutionStatus(str, Enum):
    NEXT = "NEXT"
    COMPLETED = "COMPLETED"
    WAITING = "WAITING"


@dataclass(frozen=True)
class StepExecutionResult:
    status: StepExecutionStatus
    next_step_id: str | None = None
