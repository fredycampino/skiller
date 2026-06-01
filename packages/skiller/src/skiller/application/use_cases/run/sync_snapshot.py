import json
from dataclasses import dataclass
from enum import StrEnum

from skiller.domain.event.event_model import (
    RunSnapshotFailedPayload,
    RunSnapshotUpdatedPayload,
    RuntimeEventDraft,
    RuntimeEventType,
)
from skiller.domain.event.runtime_event_store_port import RuntimeEventStorePort
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.step.run_step_model import find_run_step, validate_skill_snapshot
from skiller.domain.step.runner_port import RunnerPort


class SyncSnapshotStatus(StrEnum):
    UPDATED = "UPDATED"
    UNCHANGED = "UNCHANGED"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    FLOW_LOAD_FAILED = "FLOW_LOAD_FAILED"
    INVALID_FLOW = "INVALID_FLOW"
    CURRENT_STEP_NOT_FOUND = "CURRENT_STEP_NOT_FOUND"


@dataclass(frozen=True)
class SyncSnapshotResult:
    status: SyncSnapshotStatus
    run_id: str
    error: str | None = None


class SyncSnapshotUseCase:
    def __init__(
        self,
        *,
        store: RunStorePort,
        runner: RunnerPort,
        events: RuntimeEventStorePort,
    ) -> None:
        self.store = store
        self.runner = runner
        self.events = events

    def execute(self, run_id: str) -> SyncSnapshotResult:
        state = self.store.get_snapshot_sync_state(run_id)
        if state is None:
            return SyncSnapshotResult(
                status=SyncSnapshotStatus.RUN_NOT_FOUND,
                run_id=run_id,
                error=f"Run '{run_id}' not found",
            )

        try:
            raw_flow = self.runner.load(state.source, state.ref)
        except (FileNotFoundError, ValueError) as exc:
            error = f"Could not sync snapshot '{state.ref}': {exc}"
            return SyncSnapshotResult(
                status=SyncSnapshotStatus.FLOW_LOAD_FAILED,
                run_id=state.run_id,
                error=error,
            )

        try:
            snapshot = validate_skill_snapshot(raw_flow)
        except ValueError as exc:
            error = f"Could not sync snapshot '{state.ref}': {exc}"
            self._emit_failed(state.run_id, state.source, state.ref, error)
            return SyncSnapshotResult(
                status=SyncSnapshotStatus.INVALID_FLOW,
                run_id=state.run_id,
                error=error,
            )

        if state.current is not None:
            raw_steps = snapshot.get("steps", [])
            try:
                find_run_step(raw_steps, state.current)
            except ValueError as exc:
                error = f"Could not sync snapshot '{state.ref}': {exc}"
                return SyncSnapshotResult(
                    status=SyncSnapshotStatus.CURRENT_STEP_NOT_FOUND,
                    run_id=state.run_id,
                    error=error,
                )

        if _canonical_snapshot(state.snapshot) == _canonical_snapshot(snapshot):
            return SyncSnapshotResult(
                status=SyncSnapshotStatus.UNCHANGED,
                run_id=state.run_id,
            )

        self.store.update_snapshot(state.run_id, snapshot)
        self.events.append_event(
            RuntimeEventDraft(
                run_id=state.run_id,
                type=RuntimeEventType.RUN_SNAPSHOT_UPDATED,
                payload=RunSnapshotUpdatedPayload(
                    source=state.source,
                    ref=state.ref,
                ),
            )
        )
        return SyncSnapshotResult(
            status=SyncSnapshotStatus.UPDATED,
            run_id=state.run_id,
        )

    def _emit_failed(
        self,
        run_id: str,
        source: str,
        ref: str,
        error: str,
    ) -> None:
        self.events.append_event(
            RuntimeEventDraft(
                run_id=run_id,
                type=RuntimeEventType.RUN_SNAPSHOT_FAILED,
                payload=RunSnapshotFailedPayload(
                    source=source,
                    ref=ref,
                    error=error,
                ),
            )
        )


def _canonical_snapshot(snapshot: dict[str, object]) -> str:
    return json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
