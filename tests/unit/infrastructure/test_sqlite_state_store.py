import sqlite3

import pytest

from skiller.domain.run_context_model import RunContext
from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore

pytestmark = pytest.mark.unit


def test_init_db_drops_legacy_current_step_column(tmp_path) -> None:
    db_path = tmp_path / "legacy.db"

    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE runs (
              id TEXT PRIMARY KEY,
              skill_source TEXT NOT NULL,
              skill_ref TEXT NOT NULL,
              skill_snapshot_json TEXT NOT NULL,
              status TEXT NOT NULL,
              current TEXT,
              current_step INTEGER NOT NULL DEFAULT 0,
              inputs_json TEXT NOT NULL DEFAULT '{}',
              cancel_reason TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              finished_at TEXT
            );

            INSERT INTO runs (
              id,
              skill_source,
              skill_ref,
              skill_snapshot_json,
              status,
              current,
              current_step,
              inputs_json,
              cancel_reason,
              created_at,
              updated_at
            )
            VALUES (
              'run-1',
              'internal',
              'demo',
              '{"steps":[{"id":"start","type":"notify"}]}',
              'RUNNING',
              'start',
              3,
              '{}',
              NULL,
              '2026-03-11 10:00:00',
              '2026-03-11 10:00:00'
            );
            """
        )

    store = SqliteStateStore(str(db_path))
    store.init_db()

    with sqlite3.connect(db_path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(runs)").fetchall()]

    assert "current_step" not in columns

    run = store.get_run("run-1")

    assert run is not None
    assert run.current == "start"
    assert not hasattr(run, "current_step")


def test_get_run_rebuilds_switch_result_from_events(tmp_path) -> None:
    db_path = tmp_path / "switch.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()

    run_id = store.create_run(
        "internal",
        "demo",
        {"steps": [{"id": "start", "type": "switch"}]},
        RunContext(inputs={"repo": "acme"}, results={}),
        run_id="550e8400-e29b-41d4-a716-446655440001",
    )
    store.append_event(
        "SWITCH_DECISION",
        {
            "step": "start",
            "value": "retry",
            "next": "retry_notice",
        },
        run_id=run_id,
    )

    run = store.get_run(run_id)

    assert run is not None
    assert run.context.results["start"] == {
        "value": "retry",
        "next": "retry_notice",
    }


def test_get_run_rebuilds_when_result_from_events(tmp_path) -> None:
    db_path = tmp_path / "when.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()

    run_id = store.create_run(
        "internal",
        "demo",
        {"steps": [{"id": "start", "type": "when"}]},
        RunContext(inputs={"repo": "acme"}, results={}),
        run_id="550e8400-e29b-41d4-a716-446655440002",
    )
    store.append_event(
        "WHEN_DECISION",
        {
            "step": "start",
            "value": 85,
            "next": "good",
            "branch": 1,
            "op": "gt",
            "right": 70,
        },
        run_id=run_id,
    )

    run = store.get_run(run_id)

    assert run is not None
    assert run.context.results["start"] == {
        "value": 85,
        "next": "good",
    }


def test_create_run_uses_explicit_run_id(tmp_path) -> None:
    db_path = tmp_path / "explicit-id.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()
    explicit_run_id = "550e8400-e29b-41d4-a716-446655440003"

    run_id = store.create_run(
        "internal",
        "demo",
        {"steps": [{"id": "start", "type": "notify"}]},
        RunContext(inputs={}, results={}),
        run_id=explicit_run_id,
    )

    run = store.get_run(explicit_run_id)

    assert run_id == explicit_run_id
    assert run is not None
    assert run.id == explicit_run_id


def test_create_run_rejects_duplicate_run_id(tmp_path) -> None:
    db_path = tmp_path / "duplicate-id.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()
    skill_snapshot = {"steps": [{"id": "start", "type": "notify"}]}
    context = RunContext(inputs={}, results={})
    run_id = "550e8400-e29b-41d4-a716-446655440004"

    store.create_run("internal", "demo", skill_snapshot, context, run_id=run_id)

    with pytest.raises(ValueError, match=f"Run '{run_id}' already exists"):
        store.create_run("internal", "demo", skill_snapshot, context, run_id=run_id)
