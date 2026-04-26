from dataclasses import dataclass
from enum import Enum

from skiller.application.ports.run_store_port import RunStorePort


class DeleteRunStatus(str, Enum):
    DELETED = "DELETED"
    INVALID_RUN_ID = "INVALID_RUN_ID"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"


@dataclass(frozen=True)
class DeleteRunResult:
    status: DeleteRunStatus
    run_id: str
    error: str | None = None


class DeleteRunUseCase:
    def __init__(self, store: RunStorePort) -> None:
        self.store = store

    def execute(self, run_id: str) -> DeleteRunResult:
        normalized = run_id.strip()
        if not normalized:
            return DeleteRunResult(
                status=DeleteRunStatus.INVALID_RUN_ID,
                run_id=run_id,
                error="run_id is required",
            )

        deleted = self.store.delete_run(normalized)
        if not deleted:
            return DeleteRunResult(
                status=DeleteRunStatus.RUN_NOT_FOUND,
                run_id=normalized,
                error=f"Run '{normalized}' not found",
            )

        return DeleteRunResult(status=DeleteRunStatus.DELETED, run_id=normalized)
