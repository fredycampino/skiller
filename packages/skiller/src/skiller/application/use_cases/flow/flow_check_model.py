from dataclasses import dataclass
from enum import Enum
from typing import Any

from skiller.domain.flow.flow_raw_definition import FlowRawStepDefinition


class FlowCheckStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"


@dataclass(frozen=True)
class FlowCheckError:
    code: str
    message: str


@dataclass(frozen=True)
class FlowCheckResult:
    status: FlowCheckStatus
    errors: list[FlowCheckError]


@dataclass(frozen=True)
class FlowShapeCheck:
    start: str
    steps: tuple[FlowRawStepDefinition, ...] | None
    can_continue: bool


@dataclass(frozen=True)
class ParsedFlowStep:
    index: int
    step_id: str
    step_type: str
    body: dict[str, Any]
