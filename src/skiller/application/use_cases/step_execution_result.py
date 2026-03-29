from dataclasses import dataclass
from enum import Enum

from skiller.domain.step_execution_model import StepExecution


class StepExecutionStatus(str, Enum):
    NEXT = "NEXT"
    COMPLETED = "COMPLETED"
    WAITING = "WAITING"


@dataclass(frozen=True)
class StepAdvance:
    status: StepExecutionStatus
    next_step_id: str | None = None
    execution: StepExecution | None = None
