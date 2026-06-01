import pytest

from skiller.application.use_cases.run.sync_snapshot import (
    SyncSnapshotStatus,
    SyncSnapshotUseCase,
)
from skiller.domain.event.event_model import (
    RunSnapshotFailedPayload,
    RunSnapshotUpdatedPayload,
    RuntimeEventDraft,
    RuntimeEventType,
)
from skiller.domain.run.run_model import RunSnapshotSyncState

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self, state: RunSnapshotSyncState | None) -> None:
        self.state = state
        self.updated: list[dict[str, object]] = []

    def get_snapshot_sync_state(self, run_id: str) -> RunSnapshotSyncState | None:
        _ = run_id
        return self.state

    def update_snapshot(self, run_id: str, snapshot: dict[str, object]) -> None:
        self.updated.append(
            {
                "run_id": run_id,
                "snapshot": snapshot,
            }
        )


class _FakeRunner:
    def __init__(self, flow: object) -> None:
        self.flow = flow
        self.load_calls: list[tuple[str, str]] = []

    def load(self, source: str, ref: str) -> object:
        self.load_calls.append((source, ref))
        if isinstance(self.flow, Exception):
            raise self.flow
        return self.flow


class _FakeEvents:
    def __init__(self) -> None:
        self.events: list[RuntimeEventDraft] = []

    def append_event(self, event: RuntimeEventDraft) -> str:
        self.events.append(event)
        return "event-1"


def test_sync_snapshot_updates_only_snapshot_when_current_exists() -> None:
    flow = {
        "start": "ask_user",
        "steps": [
            {"wait_input": "ask_user", "prompt": "New prompt", "next": "done"},
            {"assign": "done", "values": {"status": "closed"}},
        ],
    }
    store = _FakeStore(
        RunSnapshotSyncState(
            run_id="run-1",
            source="internal",
            ref="mono",
            current="ask_user",
            snapshot={
                "start": "ask_user",
                "steps": [
                    {"wait_input": "ask_user", "prompt": "Old prompt", "next": "done"},
                    {"assign": "done", "values": {"status": "closed"}},
                ],
            },
        )
    )
    runner = _FakeRunner(flow)
    events = _FakeEvents()
    use_case = SyncSnapshotUseCase(store=store, runner=runner, events=events)

    result = use_case.execute("run-1")

    assert result.status == SyncSnapshotStatus.UPDATED
    assert runner.load_calls == [("internal", "mono")]
    assert store.updated == [{"run_id": "run-1", "snapshot": flow}]
    assert len(events.events) == 1
    event = events.events[0]
    assert event.type == RuntimeEventType.RUN_SNAPSHOT_UPDATED
    assert isinstance(event.payload, RunSnapshotUpdatedPayload)
    assert event.payload.source == "internal"
    assert event.payload.ref == "mono"


def test_sync_snapshot_does_not_update_when_snapshot_is_unchanged() -> None:
    flow = {
        "start": "ask_user",
        "steps": [
            {"wait_input": "ask_user", "prompt": "New prompt", "next": "done"},
            {"assign": "done", "values": {"status": "closed"}},
        ],
    }
    store = _FakeStore(
        RunSnapshotSyncState(
            run_id="run-1",
            source="internal",
            ref="mono",
            current="ask_user",
            snapshot=flow,
        )
    )
    events = _FakeEvents()
    use_case = SyncSnapshotUseCase(store=store, runner=_FakeRunner(flow), events=events)

    result = use_case.execute("run-1")

    assert result.status == SyncSnapshotStatus.UNCHANGED
    assert store.updated == []
    assert events.events == []


def test_sync_snapshot_keeps_snapshot_when_current_is_missing() -> None:
    flow = {
        "start": "ask_user",
        "steps": [
            {"wait_input": "ask_user", "prompt": "New prompt", "next": "done"},
            {"assign": "done", "values": {"status": "closed"}},
        ],
    }
    store = _FakeStore(
        RunSnapshotSyncState(
            run_id="run-1",
            source="internal",
            ref="mono",
            current="support_agent",
            snapshot={},
        )
    )
    events = _FakeEvents()
    use_case = SyncSnapshotUseCase(
        store=store,
        runner=_FakeRunner(flow),
        events=events,
    )

    result = use_case.execute("run-1")

    assert result.status == SyncSnapshotStatus.CURRENT_STEP_NOT_FOUND
    assert store.updated == []
    assert result.error == "Could not sync snapshot 'mono': step 'support_agent' was not found"
    assert events.events == []


def test_sync_snapshot_reports_load_failure() -> None:
    store = _FakeStore(
        RunSnapshotSyncState(
            run_id="run-1",
            source="internal",
            ref="mono",
            current="ask_user",
            snapshot={},
        )
    )
    events = _FakeEvents()
    use_case = SyncSnapshotUseCase(
        store=store,
        runner=_FakeRunner(FileNotFoundError("missing flow")),
        events=events,
    )

    result = use_case.execute("run-1")

    assert result.status == SyncSnapshotStatus.FLOW_LOAD_FAILED
    assert store.updated == []
    assert events.events == []


def test_sync_snapshot_reports_invalid_flow() -> None:
    store = _FakeStore(
        RunSnapshotSyncState(
            run_id="run-1",
            source="internal",
            ref="mono",
            current="ask_user",
            snapshot={},
        )
    )
    events = _FakeEvents()
    use_case = SyncSnapshotUseCase(
        store=store,
        runner=_FakeRunner({"start": "ask_user", "steps": []}),
        events=events,
    )

    result = use_case.execute("run-1")

    assert result.status == SyncSnapshotStatus.INVALID_FLOW
    assert store.updated == []
    assert len(events.events) == 1
    event = events.events[0]
    assert event.type == RuntimeEventType.RUN_SNAPSHOT_FAILED
    assert isinstance(event.payload, RunSnapshotFailedPayload)
    assert event.payload.source == "internal"
    assert event.payload.ref == "mono"
    assert event.payload.error == result.error
