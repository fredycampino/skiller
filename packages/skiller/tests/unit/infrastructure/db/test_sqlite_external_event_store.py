import sqlite3

import pytest

from skiller.domain.run.run_context_model import RunContext
from skiller.domain.wait.match_type import MatchType
from skiller.domain.wait.source_type import SourceType
from skiller.infrastructure.db.sqlite_external_event_store import SqliteExternalEventStore
from skiller.infrastructure.db.sqlite_runtime_bootstrap import SqliteRuntimeBootstrap
from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore

pytestmark = pytest.mark.unit


def test_external_event_store_creates_pending_event_and_hides_consumed_event(tmp_path) -> None:
    db_path = tmp_path / "external-events.db"
    run_store = SqliteStateStore(str(db_path))
    external_event_store = SqliteExternalEventStore(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()

    run_id = run_store.create_run(
        "internal",
        "skill",
        {"start": "done", "steps": [{"notify": "done", "message": "ok"}]},
        RunContext(inputs={}, step_executions={}),
        run_id="550e8400-e29b-41d4-a716-446655440011",
    )
    event_id = external_event_store.create_external_event(
        source_type=SourceType.CHANNEL,
        source_name="whatsapp",
        match_type=MatchType.CHANNEL_KEY,
        match_key="chat-1",
        payload={"text": "hola"},
        external_id="msg-1",
        dedup_key="msg-1",
    )

    event = external_event_store.get_latest_external_event(
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

    consumed = external_event_store.consume_external_event(event_id, run_id=run_id)

    event_after_consume = external_event_store.get_latest_external_event(
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


def test_external_event_store_returns_oldest_pending_match_first(tmp_path) -> None:
    db_path = tmp_path / "external-events-order.db"
    external_event_store = SqliteExternalEventStore(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()

    first_event_id = external_event_store.create_external_event(
        source_type=SourceType.CHANNEL,
        source_name="whatsapp",
        match_type=MatchType.CHANNEL_KEY,
        match_key="chat-1",
        payload={"text": "first"},
        external_id="msg-1",
        dedup_key="msg-1",
    )
    second_event_id = external_event_store.create_external_event(
        source_type=SourceType.CHANNEL,
        source_name="whatsapp",
        match_type=MatchType.CHANNEL_KEY,
        match_key="chat-1",
        payload={"text": "second"},
        external_id="msg-2",
        dedup_key="msg-2",
    )

    event = external_event_store.get_latest_external_event(
        source_type=SourceType.CHANNEL,
        source_name="whatsapp",
        match_type=MatchType.CHANNEL_KEY,
        match_key="chat-1",
    )

    assert event is not None
    assert event["id"] == first_event_id
    assert event["payload"] == {"text": "first"}
    assert second_event_id != first_event_id
