import sqlite3

import pytest

from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import RunStatus
from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore
from skiller.infrastructure.db.sqlite_webhook_registry import SqliteWebhookRegistry

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
    assert "results_json" in columns
    assert "steering_messages_json" in columns

    run = store.get_run("run-1")

    assert run is not None
    assert run.current == "start"
    assert not hasattr(run, "current_step")


def test_get_run_uses_persisted_results_json(tmp_path) -> None:
    db_path = tmp_path / "persisted-results.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()

    run_id = store.create_run(
        "internal",
        "demo",
        {"steps": [{"id": "start", "type": "switch"}]},
        RunContext(inputs={"repo": "acme"}, results={}),
        run_id="550e8400-e29b-41d4-a716-446655440001",
    )
    store.update_run(
        run_id,
        status=RunStatus.RUNNING,
        current="start",
        context=RunContext(
            inputs={"repo": "acme"},
            results={"start": {"value": "retry", "next": "retry_notice"}},
        ),
    )

    run = store.get_run(run_id)

    assert run is not None
    assert run.context.results["start"] == {
        "value": "retry",
        "next": "retry_notice",
    }


def test_get_run_uses_persisted_when_result(tmp_path) -> None:
    db_path = tmp_path / "persisted-when.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()

    run_id = store.create_run(
        "internal",
        "demo",
        {"steps": [{"id": "start", "type": "when"}]},
        RunContext(inputs={"repo": "acme"}, results={}),
        run_id="550e8400-e29b-41d4-a716-446655440002",
    )
    store.update_run(
        run_id,
        status=RunStatus.RUNNING,
        current="start",
        context=RunContext(
            inputs={"repo": "acme"},
            results={"start": {"value": 85, "next": "good"}},
        ),
    )

    run = store.get_run(run_id)

    assert run is not None
    assert run.context.results["start"] == {
        "value": 85,
        "next": "good",
    }


def test_update_run_persists_context_results_and_steering_messages(tmp_path) -> None:
    db_path = tmp_path / "persisted-context.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()

    run_id = store.create_run(
        "internal",
        "demo",
        {"steps": [{"id": "start", "type": "notify"}]},
        RunContext(inputs={"repo": "acme"}, results={}),
        run_id="550e8400-e29b-41d4-a716-446655440005",
    )
    context = RunContext(
        inputs={"repo": "acme"},
        results={"start": {"message": "ok"}},
        steering_messages=["be concise"],
    )

    store.update_run(run_id, status=RunStatus.RUNNING, current="start", context=context)

    run = store.get_run(run_id)

    assert run is not None
    assert run.context.results == {"start": {"message": "ok"}}
    assert run.context.steering_messages == ["be concise"]


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


def test_list_runs_returns_recent_runs_first(tmp_path) -> None:
    db_path = tmp_path / "runs.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()

    first_run_id = "550e8400-e29b-41d4-a716-446655440010"
    second_run_id = "550e8400-e29b-41d4-a716-446655440011"

    store.create_run(
        "internal",
        "notify_test",
        {"steps": [{"id": "start", "type": "notify"}]},
        RunContext(inputs={}, results={}),
        run_id=first_run_id,
    )
    store.create_run(
        "internal",
        "wait_input_test",
        {"steps": [{"id": "start", "type": "wait_input"}]},
        RunContext(inputs={}, results={}),
        run_id=second_run_id,
    )
    store.update_run(first_run_id, status=RunStatus.SUCCEEDED)
    store.update_run(second_run_id, status=RunStatus.WAITING)

    runs = store.list_runs(limit=20)

    assert [run.id for run in runs] == [second_run_id, first_run_id]
    assert runs[0].skill_ref == "wait_input_test"
    assert runs[1].skill_ref == "notify_test"


def test_list_runs_can_filter_by_status(tmp_path) -> None:
    db_path = tmp_path / "runs-filter.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()

    waiting_run_id = "550e8400-e29b-41d4-a716-446655440012"
    failed_run_id = "550e8400-e29b-41d4-a716-446655440013"

    store.create_run(
        "internal",
        "wait_input_test",
        {"steps": [{"id": "start", "type": "wait_input"}]},
        RunContext(inputs={}, results={}),
        run_id=waiting_run_id,
    )
    store.create_run(
        "internal",
        "pull_request",
        {"steps": [{"id": "start", "type": "mcp"}]},
        RunContext(inputs={}, results={}),
        run_id=failed_run_id,
    )
    store.update_run(waiting_run_id, status=RunStatus.WAITING)
    store.update_run(failed_run_id, status=RunStatus.FAILED)

    runs = store.list_runs(limit=20, statuses=["waiting"])

    assert [run.id for run in runs] == [waiting_run_id]
    assert runs[0].status == RunStatus.WAITING.value


def test_get_run_uses_persisted_input_result(tmp_path) -> None:
    db_path = tmp_path / "persisted-input.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()

    run_id = store.create_run(
        "internal",
        "chat",
        {"steps": [{"id": "start", "type": "wait_input"}]},
        RunContext(inputs={}, results={}),
        run_id="550e8400-e29b-41d4-a716-446655440099",
    )
    store.update_run(
        run_id,
        status=RunStatus.RUNNING,
        current="start",
        context=RunContext(
            inputs={},
            results={
                "start": {
                    "ok": True,
                    "prompt": "Write a message",
                    "payload": {"text": "hola"},
                    "input_event_id": "input-1",
                }
            },
        ),
    )

    run = store.get_run(run_id)

    assert run is not None
    assert run.context.results["start"] == {
        "ok": True,
        "prompt": "Write a message",
        "payload": {"text": "hola"},
        "input_event_id": "input-1",
    }


def test_sqlite_webhook_registry_lists_registered_webhooks(tmp_path) -> None:
    db_path = tmp_path / "webhooks.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()
    registry = SqliteWebhookRegistry(str(db_path))

    registry.register_webhook("github-ci", "secret-1")
    registry.register_webhook("market-signal", "secret-2")

    webhooks = registry.list_webhook_registrations()

    assert [item["webhook"] for item in webhooks] == ["github-ci", "market-signal"]
    assert all("created_at" in item for item in webhooks)
