import sqlite3

import pytest

from skiller.domain.match_type import MatchType
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import RunStatus
from skiller.domain.source_type import SourceType
from skiller.domain.step_execution_model import (
    NotifyOutput,
    StepExecution,
    SwitchOutput,
    WaitInputOutput,
    WhenOutput,
)
from skiller.domain.step_type import StepType
from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore
from skiller.infrastructure.db.sqlite_webhook_registry import SqliteWebhookRegistry

pytestmark = pytest.mark.unit


def _switch_execution(next_step_id: str, value: object) -> StepExecution:
    return StepExecution(
        step_type=StepType.SWITCH,
        input={"value": value},
        evaluation={"next_step_id": next_step_id},
        output=SwitchOutput(text=f"Route selected: {next_step_id}.", next_step_id=next_step_id),
    )


def _when_execution(next_step_id: str, value: object) -> StepExecution:
    return StepExecution(
        step_type=StepType.WHEN,
        input={"value": value},
        evaluation={"next_step_id": next_step_id},
        output=WhenOutput(text=f"Route selected: {next_step_id}.", next_step_id=next_step_id),
    )


def _notify_execution(message: str) -> StepExecution:
    return StepExecution(
        step_type=StepType.NOTIFY,
        input={"message": message},
        evaluation={},
        output=NotifyOutput(text=message, message=message),
    )


def _wait_input_execution(
    prompt: str, payload: dict[str, object], input_event_id: str
) -> StepExecution:
    return StepExecution(
        step_type=StepType.WAIT_INPUT,
        input={"prompt": prompt},
        evaluation={"input_event_id": input_event_id},
        output=WaitInputOutput(text="Input received.", prompt=prompt, payload=payload),
    )


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
              '{"start":"show_message","steps":[{"notify":"show_message"}]}',
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
    assert "step_executions_json" in columns
    assert "steering_messages_json" in columns

    run = store.get_run("run-1")

    assert run is not None
    assert run.current == "start"
    assert not hasattr(run, "current_step")


def test_get_run_uses_persisted_step_executions_json(tmp_path) -> None:
    db_path = tmp_path / "persisted-results.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()

    run_id = store.create_run(
        "internal",
        "demo",
        {"start": "decide_action", "steps": [{"switch": "decide_action"}]},
        RunContext(inputs={"repo": "acme"}, step_executions={}),
        run_id="550e8400-e29b-41d4-a716-446655440001",
    )
    store.update_run(
        run_id,
        status=RunStatus.RUNNING,
        current="start",
        context=RunContext(
            inputs={"repo": "acme"},
            step_executions={"start": _switch_execution("retry_notice", "retry")},
        ),
    )

    run = store.get_run(run_id)

    assert run is not None
    assert run.context.step_executions["start"].to_persisted_dict() == _switch_execution(
        "retry_notice", "retry"
    ).to_persisted_dict()


def test_get_run_uses_persisted_when_result(tmp_path) -> None:
    db_path = tmp_path / "persisted-when.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()

    run_id = store.create_run(
        "internal",
        "demo",
        {"start": "decide_score", "steps": [{"when": "decide_score"}]},
        RunContext(inputs={"repo": "acme"}, step_executions={}),
        run_id="550e8400-e29b-41d4-a716-446655440002",
    )
    store.update_run(
        run_id,
        status=RunStatus.RUNNING,
        current="start",
        context=RunContext(
            inputs={"repo": "acme"},
            step_executions={"start": _when_execution("good", 85)},
        ),
    )

    run = store.get_run(run_id)

    assert run is not None
    assert run.context.step_executions["start"].to_persisted_dict() == _when_execution(
        "good", 85
    ).to_persisted_dict()


def test_update_run_persists_context_results_and_steering_messages(tmp_path) -> None:
    db_path = tmp_path / "persisted-context.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()

    run_id = store.create_run(
        "internal",
        "demo",
        {"start": "show_message", "steps": [{"notify": "show_message"}]},
        RunContext(inputs={"repo": "acme"}, step_executions={}),
        run_id="550e8400-e29b-41d4-a716-446655440005",
    )
    context = RunContext(
        inputs={"repo": "acme"},
        step_executions={"start": _notify_execution("ok")},
        steering_messages=["be concise"],
    )

    store.update_run(run_id, status=RunStatus.RUNNING, current="start", context=context)

    run = store.get_run(run_id)

    assert run is not None
    assert run.context.step_executions["start"].to_persisted_dict() == _notify_execution(
        "ok"
    ).to_persisted_dict()
    assert run.context.steering_messages == ["be concise"]


def test_create_run_uses_explicit_run_id(tmp_path) -> None:
    db_path = tmp_path / "explicit-id.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()
    explicit_run_id = "550e8400-e29b-41d4-a716-446655440003"

    run_id = store.create_run(
        "internal",
        "demo",
        {"start": "show_message", "steps": [{"notify": "show_message"}]},
        RunContext(inputs={}, step_executions={}),
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
    skill_snapshot = {"start": "show_message", "steps": [{"notify": "show_message"}]}
    context = RunContext(inputs={}, step_executions={})
    run_id = "550e8400-e29b-41d4-a716-446655440004"

    store.create_run("internal", "demo", skill_snapshot, context, run_id=run_id)

    with pytest.raises(ValueError, match=f"Run '{run_id}' already exists"):
        store.create_run("internal", "demo", skill_snapshot, context, run_id=run_id)


def test_get_run_uses_persisted_input_result(tmp_path) -> None:
    db_path = tmp_path / "persisted-input.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()

    run_id = store.create_run(
        "internal",
        "chat",
        {"start": "ask_user", "steps": [{"wait_input": "ask_user"}]},
        RunContext(inputs={}, step_executions={}),
        run_id="550e8400-e29b-41d4-a716-446655440099",
    )
    store.update_run(
        run_id,
        status=RunStatus.RUNNING,
        current="start",
        context=RunContext(
            inputs={},
            step_executions={
                "start": _wait_input_execution("Write a message", {"text": "hola"}, "input-1")
            },
        ),
    )

    run = store.get_run(run_id)

    assert run is not None
    assert run.context.step_executions["start"].to_persisted_dict() == _wait_input_execution(
        "Write a message", {"text": "hola"}, "input-1"
    ).to_persisted_dict()


def test_init_db_creates_normalized_waits_and_external_events_schema(tmp_path) -> None:
    db_path = tmp_path / "normalized-schema.db"
    store = SqliteStateStore(str(db_path))

    store.init_db()

    with sqlite3.connect(db_path) as conn:
        waits_columns = [row[1] for row in conn.execute("PRAGMA table_info(waits)").fetchall()]
        external_event_columns = [
            row[1] for row in conn.execute("PRAGMA table_info(external_events)").fetchall()
        ]
        external_receipt_columns = [
            row[1] for row in conn.execute("PRAGMA table_info(external_receipts)").fetchall()
        ]

    assert waits_columns == [
        "id",
        "run_id",
        "step_id",
        "wait_type",
        "source_type",
        "source_name",
        "match_type",
        "match_key",
        "status",
        "created_at",
        "expires_at",
        "resolved_at",
    ]
    assert external_event_columns == [
        "id",
        "source_type",
        "source_name",
        "match_type",
        "match_key",
        "run_id",
        "step_id",
        "external_id",
        "dedup_key",
        "status",
        "consumed_by_run_id",
        "consumed_at",
        "payload_json",
        "created_at",
    ]
    assert external_receipt_columns == [
        "dedup_key",
        "source_type",
        "source_name",
        "match_type",
        "match_key",
        "payload_json",
        "created_at",
    ]


def test_external_event_is_created_pending_and_removed_from_pending_lookup_when_consumed(
    tmp_path,
) -> None:
    db_path = tmp_path / "external-events.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()

    run_id = store.create_run(
        "internal",
        "skill",
        {"start": "done", "steps": [{"notify": "done", "message": "ok"}]},
        RunContext(inputs={}, step_executions={}),
        run_id="550e8400-e29b-41d4-a716-446655440011",
    )
    event_id = store.create_external_event(
        source_type=SourceType.CHANNEL,
        source_name="whatsapp",
        match_type=MatchType.CHANNEL_KEY,
        match_key="chat-1",
        payload={"text": "hola"},
        external_id="msg-1",
        dedup_key="msg-1",
    )

    event = store.get_latest_external_event(
        source_type=SourceType.CHANNEL,
        source_name="whatsapp",
        match_type=MatchType.CHANNEL_KEY,
        match_key="chat-1",
    )

    assert event is not None
    assert event["id"] == event_id
    assert event["status"] == "pending"
    assert event["consumed_by_run_id"] is None
    assert event["consumed_at"] is None

    consumed = store.consume_external_event(event_id, run_id=run_id)

    event_after_consume = store.get_latest_external_event(
        source_type=SourceType.CHANNEL,
        source_name="whatsapp",
        match_type=MatchType.CHANNEL_KEY,
        match_key="chat-1",
    )

    assert consumed is True
    assert event_after_consume is None

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT status, consumed_by_run_id, consumed_at
            FROM external_events
            WHERE id = ?
            """,
            (event_id,),
        ).fetchone()

    assert row is not None
    assert row[0] == "consumed"
    assert row[1] == run_id
    assert row[2] is not None


def test_get_latest_external_event_returns_oldest_pending_match_first(tmp_path) -> None:
    db_path = tmp_path / "external-events-order.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()

    first_event_id = store.create_external_event(
        source_type=SourceType.CHANNEL,
        source_name="whatsapp",
        match_type=MatchType.CHANNEL_KEY,
        match_key="chat-1",
        payload={"text": "first"},
        external_id="msg-1",
        dedup_key="msg-1",
    )
    second_event_id = store.create_external_event(
        source_type=SourceType.CHANNEL,
        source_name="whatsapp",
        match_type=MatchType.CHANNEL_KEY,
        match_key="chat-1",
        payload={"text": "second"},
        external_id="msg-2",
        dedup_key="msg-2",
    )

    event = store.get_latest_external_event(
        source_type=SourceType.CHANNEL,
        source_name="whatsapp",
        match_type=MatchType.CHANNEL_KEY,
        match_key="chat-1",
    )

    assert event is not None
    assert event["id"] == first_event_id
    assert event["payload"] == {"text": "first"}
    assert second_event_id != first_event_id


def test_sqlite_webhook_registry_lists_registered_webhooks(tmp_path) -> None:
    db_path = tmp_path / "webhooks.db"
    registry = SqliteWebhookRegistry(str(db_path))
    registry.init_db()

    registry.register_webhook("github-ci", "secret-1")
    registry.register_webhook("market-signal", "secret-2")

    webhooks = registry.list_webhook_registrations()

    assert sorted(item["webhook"] for item in webhooks) == ["github-ci", "market-signal"]
    assert all("created_at" in item for item in webhooks)
