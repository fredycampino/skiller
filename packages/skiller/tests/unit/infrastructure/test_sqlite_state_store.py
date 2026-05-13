import sqlite3

import pytest

from skiller.domain.agent.agent_context_model import AgentToolCallPayload
from skiller.domain.event.event_model import (
    AgentEventPayload,
    AgentLifecyclePayload,
    RunCreatedPayload,
    RuntimeEventDraft,
    RuntimeEventType,
    RunWaitingPayload,
    StepStartedPayload,
)
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import RunStatus
from skiller.domain.run.steering_model import (
    SteeringAgentInterrupt,
    SteeringAgentMessage,
)
from skiller.domain.step.step_execution_model import (
    NotifyOutput,
    StepExecution,
    SwitchOutput,
    WaitInputOutput,
    WhenOutput,
)
from skiller.domain.step.step_type import StepType
from skiller.domain.wait.match_type import MatchType
from skiller.domain.wait.source_type import SourceType
from skiller.domain.wait.wait_type import WaitType
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
    assert (
        run.context.step_executions["start"].to_persisted_dict()
        == _switch_execution("retry_notice", "retry").to_persisted_dict()
    )


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
    assert (
        run.context.step_executions["start"].to_persisted_dict()
        == _when_execution("good", 85).to_persisted_dict()
    )


def test_update_run_persists_context_results_without_overwriting_steering_queue(
    tmp_path,
) -> None:
    db_path = tmp_path / "persisted-context.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()
    initial_item = SteeringAgentInterrupt()

    run_id = store.create_run(
        "internal",
        "demo",
        {"start": "show_message", "steps": [{"notify": "show_message"}]},
        RunContext(
            inputs={"repo": "acme"},
            step_executions={},
            steering_queue=[initial_item],
        ),
        run_id="550e8400-e29b-41d4-a716-446655440005",
    )
    context = RunContext(
        inputs={"repo": "acme"},
        step_executions={"start": _notify_execution("ok")},
        steering_queue=[SteeringAgentMessage(text="be concise")],
    )

    store.update_run(run_id, status=RunStatus.RUNNING, current="start", context=context)

    run = store.get_run(run_id)

    assert run is not None
    assert (
        run.context.step_executions["start"].to_persisted_dict()
        == _notify_execution("ok").to_persisted_dict()
    )
    assert run.context.steering_queue == [initial_item]


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
    assert (
        run.context.step_executions["start"].to_persisted_dict()
        == _wait_input_execution("Write a message", {"text": "hola"}, "input-1").to_persisted_dict()
    )


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


def test_update_run_terminal_status_expires_active_waits(tmp_path) -> None:
    db_path = tmp_path / "terminal-status-expires-waits.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()

    run_id = store.create_run(
        "internal",
        "whatsapp_demo",
        {"start": "listen_whatsapp", "steps": [{"wait_channel": "listen_whatsapp"}]},
        RunContext(inputs={}, step_executions={}),
        run_id="550e8400-e29b-41d4-a716-446655440012",
    )
    wait_id = store.create_wait(
        run_id,
        step_id="listen_whatsapp",
        wait_type=WaitType.CHANNEL,
        source_type=SourceType.CHANNEL,
        source_name="whatsapp",
        match_type=MatchType.CHANNEL_KEY,
        match_key="all",
    )

    store.update_run(run_id, status=RunStatus.CANCELLED, current="listen_whatsapp")

    active_wait = store.get_active_wait(
        run_id,
        "listen_whatsapp",
        wait_type=WaitType.CHANNEL,
    )

    assert active_wait is None

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT status, resolved_at
            FROM waits
            WHERE id = ?
            """,
            (wait_id,),
        ).fetchone()

    assert row is not None
    assert row[0] == "EXPIRED"
    assert row[1] is not None


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


def test_list_events_exposes_monotonic_sequence(tmp_path) -> None:
    db_path = tmp_path / "events-sequence.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()
    run_id = "550e8400-e29b-41d4-a716-446655440030"
    store.create_run(
        "internal",
        "skill",
        {"start": "done", "steps": [{"notify": "done"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=run_id,
    )

    first_event_id = store.append_event(
        RuntimeEventDraft(
            run_id=run_id,
            type=RuntimeEventType.STEP_STARTED,
            step_id="done",
            step_type="notify",
            payload=StepStartedPayload(),
        )
    )
    second_event_id = store.append_event(
        RuntimeEventDraft(
            run_id=run_id,
            type=RuntimeEventType.RUN_WAITING,
            step_id="done",
            step_type="notify",
            payload=RunWaitingPayload(output={}),
        )
    )

    events = store.list_events(run_id)
    last_event = store.get_last_event(run_id)

    assert [event.id for event in events] == [first_event_id, second_event_id]
    assert [event.run_id for event in events] == [run_id, run_id]
    assert [event.sequence for event in events] == sorted(event.sequence for event in events)
    assert events[0].sequence < events[1].sequence
    assert last_event is not None
    assert last_event.id == second_event_id
    assert last_event.run_id == run_id
    assert last_event.sequence == events[1].sequence
    assert store.list_events(run_id, after_sequence=events[0].sequence) == [events[1]]
    assert store.list_events(run_id, limit=1) == [events[0]]
    assert store.list_events(run_id, after_sequence=events[0].sequence, limit=1) == [events[1]]


def test_list_events_roundtrips_agent_event_body(tmp_path) -> None:
    db_path = tmp_path / "agent-log-events.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()
    run_id = "550e8400-e29b-41d4-a716-446655440031"
    store.create_run(
        "internal",
        "skill",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=run_id,
    )

    event_id = store.append_event(
        RuntimeEventDraft(
            run_id=run_id,
            type=RuntimeEventType.AGENT_TOOL_CALL,
            payload=AgentEventPayload(
                step_id="support_agent",
                turn_id="turn-1",
                agent_sequence=33,
                body=AgentToolCallPayload(
                    turn_id="turn-1",
                    parent_sequence=32,
                    tool_call_id="call-1",
                    tool="shell",
                    args={"command": "pwd"},
                ),
            ),
        )
    )

    events = store.list_events(run_id)

    assert len(events) == 1
    assert events[0].id == event_id
    assert events[0].step_id == "support_agent"
    assert events[0].step_type == "agent"
    assert events[0].agent_sequence == 33
    assert events[0].payload == AgentEventPayload(
        step_id="support_agent",
        turn_id="turn-1",
        agent_sequence=33,
        body=AgentToolCallPayload(
            turn_id="turn-1",
            parent_sequence=32,
            tool_call_id="call-1",
            tool="shell",
            args={"command": "pwd"},
        ),
    )
    assert events[0].model_dump(mode="json")["payload"] == {
        "type": "tool_call",
        "turn_id": "turn-1",
        "parent_sequence": 32,
        "tool_call_id": "call-1",
        "tool": "shell",
        "args": {"command": "pwd"},
    }


def test_list_events_keeps_agent_lifecycle_metadata_in_envelope(tmp_path) -> None:
    db_path = tmp_path / "agent-lifecycle-events.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()
    run_id = "550e8400-e29b-41d4-a716-446655440032"
    store.create_run(
        "internal",
        "skill",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=run_id,
    )

    store.append_event(
        RuntimeEventDraft(
            run_id=run_id,
            type=RuntimeEventType.AGENT_MAX_TURNS_EXHAUSTED,
            step_id="support_agent",
            step_type="agent",
            payload=AgentLifecyclePayload(
                turn_id="turn-29",
                stop_reason="max_turns_exhausted",
            ),
        )
    )

    event = store.list_events(run_id)[0]

    assert event.step_id == "support_agent"
    assert event.step_type == "agent"
    assert event.agent_sequence is None
    assert event.payload == AgentLifecyclePayload(
        turn_id="turn-29",
        stop_reason="max_turns_exhausted",
    )
    assert event.model_dump(mode="json")["payload"] == {
        "turn_id": "turn-29",
        "stop_reason": "max_turns_exhausted",
    }


def test_delete_run_removes_database_rows_tied_to_run(tmp_path) -> None:
    db_path = tmp_path / "delete-run.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()

    run_id = "550e8400-e29b-41d4-a716-446655440021"
    other_run_id = "550e8400-e29b-41d4-a716-446655440022"
    skill_snapshot = {"start": "wait", "steps": [{"wait_channel": "wait"}]}
    context = RunContext(inputs={}, step_executions={})
    store.create_run("internal", "skill", skill_snapshot, context, run_id=run_id)
    store.create_run("internal", "skill", skill_snapshot, context, run_id=other_run_id)
    store.append_event(
        RuntimeEventDraft(
            run_id=run_id,
            type=RuntimeEventType.RUN_CREATE,
            payload=RunCreatedPayload(skill="skill", skill_source="internal"),
        )
    )
    store.append_event(
        RuntimeEventDraft(
            run_id=other_run_id,
            type=RuntimeEventType.RUN_CREATE,
            payload=RunCreatedPayload(skill="skill", skill_source="internal"),
        )
    )
    store.create_wait(
        run_id,
        step_id="wait",
        wait_type=WaitType.CHANNEL,
        source_type=SourceType.CHANNEL,
        source_name="whatsapp",
        match_type=MatchType.CHANNEL_KEY,
        match_key="chat-1",
    )
    store.create_wait(
        other_run_id,
        step_id="wait",
        wait_type=WaitType.CHANNEL,
        source_type=SourceType.CHANNEL,
        source_name="whatsapp",
        match_type=MatchType.CHANNEL_KEY,
        match_key="chat-2",
    )
    store.create_external_event(
        source_type=SourceType.CHANNEL,
        source_name="whatsapp",
        match_type=MatchType.CHANNEL_KEY,
        match_key="chat-1",
        payload={"text": "run scoped"},
        run_id=run_id,
        step_id="wait",
        external_id="msg-1",
        dedup_key="msg-1",
    )
    store.register_external_receipt(
        "msg-1",
        SourceType.CHANNEL,
        "whatsapp",
        MatchType.CHANNEL_KEY,
        "chat-1",
        {"text": "run scoped"},
    )
    consumed_event_id = store.create_external_event(
        source_type=SourceType.CHANNEL,
        source_name="whatsapp",
        match_type=MatchType.CHANNEL_KEY,
        match_key="chat-2",
        payload={"text": "consumed by deleted run"},
        run_id=other_run_id,
        step_id="wait",
        external_id="msg-2",
        dedup_key="msg-2",
    )
    store.register_external_receipt(
        "msg-2",
        SourceType.CHANNEL,
        "whatsapp",
        MatchType.CHANNEL_KEY,
        "chat-2",
        {"text": "consumed by deleted run"},
    )
    store.consume_external_event(consumed_event_id, run_id=run_id)
    store.create_external_event(
        source_type=SourceType.CHANNEL,
        source_name="whatsapp",
        match_type=MatchType.CHANNEL_KEY,
        match_key="chat-3",
        payload={"text": "other"},
        run_id=other_run_id,
        step_id="wait",
        external_id="msg-3",
        dedup_key="msg-3",
    )
    store.register_external_receipt(
        "msg-3",
        SourceType.CHANNEL,
        "whatsapp",
        MatchType.CHANNEL_KEY,
        "chat-3",
        {"text": "other"},
    )
    deleted = store.delete_run(run_id)

    assert deleted is True
    assert store.get_run(run_id) is None
    assert store.get_run(other_run_id) is not None

    with sqlite3.connect(db_path) as conn:
        assert _count(conn, "runs", "id = ?", run_id) == 0
        assert _count(conn, "log_events", "run_id = ?", run_id) == 0
        assert _count(conn, "waits", "run_id = ?", run_id) == 0
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
        assert _count(conn, "log_events", "run_id = ?", other_run_id) == 1
        assert _count(conn, "waits", "run_id = ?", other_run_id) == 1
        assert _count(conn, "external_events", "run_id = ?", other_run_id) == 1
        assert _count(conn, "external_receipts", "dedup_key = 'msg-3'") == 1


def test_delete_run_returns_false_for_missing_run(tmp_path) -> None:
    db_path = tmp_path / "delete-missing-run.db"
    store = SqliteStateStore(str(db_path))
    store.init_db()

    deleted = store.delete_run("missing-run")

    assert deleted is False


def _count(conn: sqlite3.Connection, table: str, where: str, *params: object) -> int:
    row = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()
    assert row is not None
    return int(row[0])


def test_sqlite_webhook_registry_lists_registered_webhooks(tmp_path) -> None:
    db_path = tmp_path / "webhooks.db"
    registry = SqliteWebhookRegistry(str(db_path))
    registry.init_db()

    registry.register_webhook("github-ci", "secret-1")
    registry.register_webhook("market-signal", "secret-2")

    webhooks = registry.list_webhook_registrations()

    assert sorted(item["webhook"] for item in webhooks) == ["github-ci", "market-signal"]
    assert all("created_at" in item for item in webhooks)
