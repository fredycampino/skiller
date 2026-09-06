from dataclasses import dataclass
from enum import Enum
from typing import Any

from skiller.application.use_cases.run.resume_run import ResumeRunStatus
from skiller.domain.flow.flow_reference import FlowReference
from skiller.domain.run.run_model import RunStatus


class WorkerStartStatus(str, Enum):
    PREPARED = "PREPARED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class RunRequest:
    reference: FlowReference
    inputs: dict[str, Any]


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: RunStatus


@dataclass(frozen=True)
class WorkerStartResult:
    run_id: str
    start_status: WorkerStartStatus
    status: RunStatus


@dataclass(frozen=True)
class ResumeRunApplicationResult:
    run_id: str
    resume_status: ResumeRunStatus
    status: RunStatus
