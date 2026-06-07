import json
import sqlite3

from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import (
    Run,
    RunSnapshotSyncState,
    RunStatus,
)
from skiller.domain.run.run_status_runtime_model import RunStatusRuntime
from skiller.domain.run.run_store_port import RunStorePort
from skiller.infrastructure.db.datasource.sqlite_run_datasource import SqliteRunDatasource
from skiller.infrastructure.db.sqlite_run_mapper import build_run_from_row


class SqliteRunStorePort(RunStorePort):
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.run_datasource = SqliteRunDatasource(db_path)

    def create_run(
        self,
        source: str,
        ref: str,
        snapshot: dict[str, object],
        context: RunContext,
        *,
        run_id: str,
    ) -> str:
        snapshot_json = json.dumps(snapshot)
        inputs_json = json.dumps(context.inputs)
        step_executions_json = json.dumps(context.to_dict()["step_executions"])
        steering_queue_json = json.dumps(
            [item.to_dict() for item in context.steering_queue]
        )
        try:
            return self.run_datasource.create_run_row(
                run_id=run_id,
                source=source,
                ref=ref,
                snapshot_json=snapshot_json,
                status=RunStatus.CREATED.value,
                inputs_json=inputs_json,
                step_executions_json=step_executions_json,
                steering_queue_json=steering_queue_json,
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Run '{run_id}' already exists") from exc

    def update_run(
        self,
        run_id: str,
        *,
        status: RunStatus | None = None,
        current: str | None = None,
        context: RunContext | None = None,
    ) -> None:
        terminal_statuses = (RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED)
        status_value = status.value if status is not None else None
        finished = status in terminal_statuses
        step_executions_json = None
        cancel_reason = None
        if context is not None:
            step_executions_json = json.dumps(context.to_dict()["step_executions"])
            cancel_reason = context.cancel_reason

        self.run_datasource.update_run_row(
            run_id=run_id,
            status=status_value,
            current=current,
            step_executions_json=step_executions_json,
            cancel_reason=cancel_reason,
            finished=finished,
            expire_active_waits=finished,
        )

    def get_run(self, run_id: str) -> Run | None:
        row = self.run_datasource.get_run_row(run_id)
        if row is None:
            return None
        return build_run_from_row(row)

    def get_status(self, run_id: str) -> RunStatusRuntime | None:
        row = self.run_datasource.get_status_row(run_id)
        if row is None:
            return None
        return RunStatusRuntime(
            run_id=str(row["id"]),
            status=RunStatus(str(row["status"])),
        )

    def get_snapshot_sync_state(self, run_id: str) -> RunSnapshotSyncState | None:
        row = self.run_datasource.get_snapshot_sync_state_row(run_id)
        if row is None:
            return None
        snapshot = json.loads(row["snapshot_json"])
        if not isinstance(snapshot, dict):
            snapshot = {}
        return RunSnapshotSyncState(
            run_id=str(row["id"]),
            source=str(row["source"]),
            ref=str(row["ref"]),
            current=(str(row["current"]) if row["current"] is not None else None),
            snapshot=snapshot,
        )

    def update_snapshot(self, run_id: str, snapshot: dict[str, object]) -> None:
        snapshot_json = json.dumps(snapshot)
        self.run_datasource.update_snapshot_json(run_id, snapshot_json)

    def cleanup_run(self, run_id: str) -> bool:
        return self.run_datasource.cleanup_run(run_id)

    def delete_run(self, run_id: str) -> bool:
        return self.run_datasource.delete_run(run_id)
