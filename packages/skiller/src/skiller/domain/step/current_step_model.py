from dataclasses import dataclass
from enum import Enum
from typing import Any

from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import RunStatus
from skiller.domain.step.step_type import StepType


class CurrentStepStatus(str, Enum):
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    READY = "READY"
    DONE = "DONE"
    CANCELLED = RunStatus.CANCELLED.value
    WAITING = RunStatus.WAITING.value
    SUCCEEDED = RunStatus.SUCCEEDED.value
    FAILED = RunStatus.FAILED.value
    INVALID_SKILL = "INVALID_SKILL"
    INVALID_STEP = "INVALID_STEP"


@dataclass(frozen=True)
class CurrentStep:
    run_id: str
    step_index: int
    step_id: str
    step_type: StepType
    step: dict[str, Any]
    context: RunContext
    run_created_at: str | None = None
