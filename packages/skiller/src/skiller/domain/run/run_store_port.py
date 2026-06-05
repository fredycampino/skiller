from typing import Protocol

from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import (
    Run,
    RunSnapshotSyncState,
    RunStatus,
)
from skiller.domain.run.run_status_runtime_model import RunStatusRuntime


class RunStorePort(Protocol):
    def create_run(
        self,
        source: str,
        ref: str,
        snapshot: dict[str, object],
        context: RunContext,
        *,
        run_id: str,
    ) -> str: ...

    def update_run(
        self,
        run_id: str,
        *,
        status: RunStatus | None = None,
        current: str | None = None,
        context: RunContext | None = None,
    ) -> None: ...

    def get_run(self, run_id: str) -> Run | None: ...

    def get_status(self, run_id: str) -> RunStatusRuntime | None: ...

    def get_snapshot_sync_state(self, run_id: str) -> RunSnapshotSyncState | None: ...

    def update_snapshot(self, run_id: str, snapshot: dict[str, object]) -> None: ...

    def delete_run(self, run_id: str) -> bool: ...
