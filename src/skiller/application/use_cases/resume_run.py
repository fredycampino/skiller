from dataclasses import dataclass
from enum import Enum

from skiller.application.ports.state_store_port import StateStorePort
from skiller.domain.run_model import RunStatus


class ResumeRunStatus(str, Enum):
    RESUMED = "RESUMED"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    NOT_WAITING = "NOT_WAITING"


@dataclass(frozen=True)
class ResumeRunResult:
    status: ResumeRunStatus


class ResumeRunUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, run_id: str, *, source: str = "manual") -> ResumeRunResult:
        run = self.store.get_run(run_id)
        if run is None:
            return ResumeRunResult(status=ResumeRunStatus.RUN_NOT_FOUND)
        if run.status != RunStatus.WAITING.value:
            return ResumeRunResult(status=ResumeRunStatus.NOT_WAITING)

        self.store.update_run(run_id, status=RunStatus.RUNNING)
        return ResumeRunResult(status=ResumeRunStatus.RESUMED)
