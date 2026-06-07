import json
import sqlite3

import pytest

from skiller.domain.event.event_model import (
    RunCreatedPayload,
    RunFinishedPayload,
    RuntimeEventDraft,
    RuntimeEventType,
    StepSuccessPayload,
)
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.wait.match_type import MatchType
from skiller.domain.wait.source_type import SourceType
from skiller.domain.wait.wait_type import WaitType
from skiller.infrastructure.db.datasource.sqlite_run_datasource import (
    SqliteRunDatasource,
)
from skiller.infrastructure.db.datasource.sqlite_wait_datasource import SqliteWaitDatasource
from skiller.infrastructure.db.sqlite_external_event_store import SqliteExternalEventStore
from skiller.infrastructure.db.sqlite_run_store_port import SqliteRunStorePort
from skiller.infrastructure.db.sqlite_runtime_bootstrap import SqliteRuntimeBootstrap
from skiller.infrastructure.db.sqlite_runtime_event_store import SqliteRuntimeEventStore
from skiller.infrastructure.db.sqlite_wait_store_port import SqliteWaitStorePort

pytestmark = pytest.mark.unit


def test_cleanup_run_keeps_terminal_events_and_clears_sensitive_data(tmp_path) -> None:
    db_path = tmp_path / "cleanup-run.db"
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store = SqliteRunStorePort(str(db_path))
    event_store = SqliteRuntimeEventStore(str(db_path))
    external_event_store = SqliteExternalEventStore(str(db_path))
    datasource = SqliteRunDatasource(str(db_path))
    run_id = "550e8400-e29b-41d4-a716-446655440051"
    other_run_id = "550e8400-e29b-41d4-a716-446655440052"

    _create_run(run_store, run_id)
    _create_run(run_store, other_run_id)
    _seed_sensitive_run_data(
        db_path=str(db_path),
        run_id=run_id,
        other_run_id=other_run_id,
        event_store=event_store,
        external_event_store=external_event_store,
    )

    cleaned = datasource.cleanup_run(run_id)

    assert cleaned is True
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert run is not None
        assert json.loads(run["inputs_json"]) == {}
        assert json.loads(run["step_executions_json"]) == {}
        assert json.loads(run["steering_queue_json"]) == []
        assert run["cancel_reason"] is None
        assert _event_types(conn, run_id) == ["RUN_CREATE", "RUN_FINISHED"]
        assert _count(conn, "waits", "run_id = ?", run_id) == 0
        assert _count(conn, "agent_context_entries", "run_id = ?", run_id) == 0
        assert (
            _count(
                conn,
                "external_events",
                "run_id = ? OR consumed_by_run_id = ?",
                run_id,
                run_id,
            )
            == 0
        )
        assert _count(conn, "external_receipts", "dedup_key IN ('msg-1', 'msg-2')") == 0
        assert _count(conn, "runs", "id = ?", other_run_id) == 1
        assert _count(conn, "waits", "run_id = ?", other_run_id) == 1
        assert _count(conn, "external_events", "run_id = ?", other_run_id) == 1
        assert _count(conn, "external_receipts", "dedup_key = 'msg-3'") == 1


def test_cleanup_run_returns_false_for_missing_run(tmp_path) -> None:
    db_path = tmp_path / "cleanup-missing-run.db"
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    datasource = SqliteRunDatasource(str(db_path))

    cleaned = datasource.cleanup_run("missing-run")

    assert cleaned is False


def test_delete_run_removes_run_and_related_data(tmp_path) -> None:
    db_path = tmp_path / "delete-run.db"
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store = SqliteRunStorePort(str(db_path))
    event_store = SqliteRuntimeEventStore(str(db_path))
    external_event_store = SqliteExternalEventStore(str(db_path))
    datasource = SqliteRunDatasource(str(db_path))
    run_id = "550e8400-e29b-41d4-a716-446655440053"
    other_run_id = "550e8400-e29b-41d4-a716-446655440054"

    _create_run(run_store, run_id)
    _create_run(run_store, other_run_id)
    _seed_sensitive_run_data(
        db_path=str(db_path),
        run_id=run_id,
        other_run_id=other_run_id,
        event_store=event_store,
        external_event_store=external_event_store,
    )

    deleted = datasource.delete_run(run_id)

    assert deleted is True
    with sqlite3.connect(db_path) as conn:
        assert _count(conn, "runs", "id = ?", run_id) == 0
        assert _count(conn, "log_events", "run_id = ?", run_id) == 0
        assert _count(conn, "waits", "run_id = ?", run_id) == 0
        assert _count(conn, "agent_context_entries", "run_id = ?", run_id) == 0
        assert (
            _count(
                conn,
                "external_events",
                "run_id = ? OR consumed_by_run_id = ?",
                run_id,
                run_id,
            )
            == 0
        )
        assert _count(conn, "runs", "id = ?", other_run_id) == 1


def _create_run(run_store: SqliteRunStorePort, run_id: str) -> None:
    run_store.create_run(
        "internal",
        "skill",
        {"start": "wait", "steps": [{"wait_input": "wait"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=run_id,
    )


def _seed_sensitive_run_data(
    *,
    db_path: str,
    run_id: str,
    other_run_id: str,
    event_store: SqliteRuntimeEventStore,
    external_event_store: SqliteExternalEventStore,
) -> None:
    wait_store = SqliteWaitStorePort(SqliteWaitDatasource(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE runs
            SET
              inputs_json = ?,
              step_executions_json = ?,
              steering_queue_json = ?,
              cancel_reason = ?
            WHERE id = ?
            """,
            (
                json.dumps({"secret": "input-secret"}),
                json.dumps({"wait": {"output": {"text": "input-secret"}}}),
                json.dumps([{"type": "agent_message", "text": "input-secret"}]),
                "input-secret",
                run_id,
            ),
        )
        conn.execute(
            """
            INSERT INTO agent_context_entries (
              id,
              run_id,
              context_id,
              sequence,
              entry_type,
              message_type,
              payload_json,
              source_step_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "agent-context-1",
                run_id,
                "ctx-1",
                1,
                "message",
                "user",
                json.dumps({"text": "input-secret"}),
                "agent",
            ),
        )

    event_store.append_event(
        RuntimeEventDraft(
            run_id=run_id,
            type=RuntimeEventType.RUN_CREATE,
            payload=RunCreatedPayload(ref="skill", source="internal"),
        )
    )
    event_store.append_event(
        RuntimeEventDraft(
            run_id=run_id,
            type=RuntimeEventType.STEP_SUCCESS,
            step_id="wait",
            step_type="wait_input",
            payload=StepSuccessPayload(output={"secret": "input-secret"}),
        )
    )
    event_store.append_event(
        RuntimeEventDraft(
            run_id=run_id,
            type=RuntimeEventType.RUN_FINISHED,
            payload=RunFinishedPayload(status="SUCCEEDED"),
        )
    )
    wait_store.create_wait(
        run_id,
        step_id="wait",
        wait_type=WaitType.INPUT,
        source_type=SourceType.INPUT,
        source_name="manual",
        match_type=MatchType.RUN,
        match_key=run_id,
    )
    wait_store.create_wait(
        other_run_id,
        step_id="wait",
        wait_type=WaitType.INPUT,
        source_type=SourceType.INPUT,
        source_name="manual",
        match_type=MatchType.RUN,
        match_key=other_run_id,
    )
    external_event_store.create_external_event(
        source_type=SourceType.INPUT,
        source_name="manual",
        match_type=MatchType.RUN,
        match_key=run_id,
        payload={"text": "input-secret"},
        run_id=run_id,
        step_id="wait",
        external_id="msg-1",
        dedup_key="msg-1",
    )
    external_event_store.register_external_receipt(
        "msg-1",
        SourceType.INPUT,
        "manual",
        MatchType.RUN,
        run_id,
        {"text": "input-secret"},
    )
    consumed_event_id = external_event_store.create_external_event(
        source_type=SourceType.INPUT,
        source_name="manual",
        match_type=MatchType.RUN,
        match_key=other_run_id,
        payload={"text": "consumed by cleaned run"},
        run_id=other_run_id,
        step_id="wait",
        external_id="msg-2",
        dedup_key="msg-2",
    )
    external_event_store.register_external_receipt(
        "msg-2",
        SourceType.INPUT,
        "manual",
        MatchType.RUN,
        other_run_id,
        {"text": "consumed by cleaned run"},
    )
    external_event_store.consume_external_event(consumed_event_id, run_id=run_id)
    external_event_store.create_external_event(
        source_type=SourceType.INPUT,
        source_name="manual",
        match_type=MatchType.RUN,
        match_key=other_run_id,
        payload={"text": "other"},
        run_id=other_run_id,
        step_id="wait",
        external_id="msg-3",
        dedup_key="msg-3",
    )
    external_event_store.register_external_receipt(
        "msg-3",
        SourceType.INPUT,
        "manual",
        MatchType.RUN,
        other_run_id,
        {"text": "other"},
    )


def _event_types(conn: sqlite3.Connection, run_id: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT event_type
        FROM log_events
        WHERE run_id = ?
        ORDER BY sequence ASC
        """,
        (run_id,),
    ).fetchall()
    return [str(row[0]) for row in rows]


def _count(
    conn: sqlite3.Connection,
    table: str,
    where: str,
    *params: object,
) -> int:
    row = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()
    assert row is not None
    return int(row[0])
