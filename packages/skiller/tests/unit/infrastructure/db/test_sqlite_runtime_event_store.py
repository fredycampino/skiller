import pytest

from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessagePayload,
    AgentContextEntry,
    AgentContextEntryType,
    AgentToolCallPayload,
)
from skiller.domain.event.event_model import (
    AgentAssistantMessageContext,
    AgentBodyFinalMessage,
    AgentBodyToolMessage,
    AgentEventPayload,
    AgentLifecyclePayload,
    RuntimeEventDraft,
    RuntimeEventType,
    RunWaitingPayload,
    StepStartedPayload,
)
from skiller.domain.run.run_context_model import RunContext
from skiller.infrastructure.db.sqlite_runtime_bootstrap import SqliteRuntimeBootstrap
from skiller.infrastructure.db.sqlite_runtime_event_store import SqliteRuntimeEventStore
from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore

pytestmark = pytest.mark.unit


def test_runtime_event_store_lists_events_with_monotonic_sequence(tmp_path) -> None:
    db_path = tmp_path / "runtime-events-sequence.db"
    run_store = SqliteStateStore(str(db_path))
    runtime_event_store = SqliteRuntimeEventStore(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_id = "550e8400-e29b-41d4-a716-446655440030"
    run_store.create_run(
        "internal",
        "skill",
        {"start": "done", "steps": [{"notify": "done"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=run_id,
    )

    first_event_id = runtime_event_store.append_event(
        RuntimeEventDraft(
            run_id=run_id,
            type=RuntimeEventType.STEP_STARTED,
            step_id="done",
            step_type="notify",
            payload=StepStartedPayload(),
        )
    )
    second_event_id = runtime_event_store.append_event(
        RuntimeEventDraft(
            run_id=run_id,
            type=RuntimeEventType.RUN_WAITING,
            step_id="done",
            step_type="notify",
            payload=RunWaitingPayload(output={}),
        )
    )

    events = runtime_event_store.list_events(run_id)
    last_event = runtime_event_store.get_last_event(run_id)

    assert [event.id for event in events] == [first_event_id, second_event_id]
    assert [event.run_id for event in events] == [run_id, run_id]
    assert [event.sequence for event in events] == sorted(event.sequence for event in events)
    assert events[0].sequence < events[1].sequence
    assert last_event is not None
    assert last_event.id == second_event_id
    assert last_event.run_id == run_id
    assert last_event.sequence == events[1].sequence
    assert runtime_event_store.list_events(run_id, after_sequence=events[0].sequence) == [
        events[1]
    ]
    assert runtime_event_store.list_events(run_id, limit=1) == [events[0]]
    assert runtime_event_store.list_events(
        run_id,
        after_sequence=events[0].sequence,
        limit=1,
    ) == [events[1]]


def test_runtime_event_store_roundtrips_agent_event_body(tmp_path) -> None:
    db_path = tmp_path / "runtime-agent-events.db"
    run_store = SqliteStateStore(str(db_path))
    runtime_event_store = SqliteRuntimeEventStore(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_id = "550e8400-e29b-41d4-a716-446655440031"
    run_store.create_run(
        "internal",
        "skill",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=run_id,
    )

    event_id = runtime_event_store.append_event(
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

    events = runtime_event_store.list_events(run_id)

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


def test_runtime_event_store_keeps_agent_lifecycle_metadata_in_envelope(tmp_path) -> None:
    db_path = tmp_path / "runtime-agent-lifecycle-events.db"
    run_store = SqliteStateStore(str(db_path))
    runtime_event_store = SqliteRuntimeEventStore(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_id = "550e8400-e29b-41d4-a716-446655440032"
    run_store.create_run(
        "internal",
        "skill",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=run_id,
    )

    runtime_event_store.emit_max_turns_exhausted(
        run_id=run_id,
        step_id="support_agent",
        turn_id="turn-29",
    )

    event = runtime_event_store.list_events(run_id)[0]

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


def test_runtime_event_store_emits_assistant_message_from_agent_context_entry(tmp_path) -> None:
    db_path = tmp_path / "runtime-assistant-message.db"
    run_store = SqliteStateStore(str(db_path))
    runtime_event_store = SqliteRuntimeEventStore(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_id = "550e8400-e29b-41d4-a716-446655440033"
    run_store.create_run(
        "internal",
        "skill",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=run_id,
    )

    runtime_event_store.emit_assistant_message(
        entry=AgentContextEntry(
            id="entry-1",
            run_id=run_id,
            context_id="ctx-1",
            sequence=7,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            usage=None,
            payload=AgentAssistantMessagePayload(
                turn_id="turn-4",
                message_type="tool_calls",
                text="I will inspect.",
                total_tokens=1000,
            ),
            source_step_id="support_agent",
            created_at="2026-05-15T00:00:00Z",
        )
    )

    event = runtime_event_store.get_last_event(run_id)

    assert event is not None
    assert event.type == RuntimeEventType.AGENT_ASSISTANT_MESSAGE
    assert event.step_id == "support_agent"
    assert event.agent_sequence == 7
    assert event.payload == AgentEventPayload(
        step_id="support_agent",
        turn_id="turn-4",
        agent_sequence=7,
        body=AgentBodyToolMessage(
            total_tokens=1000,
            text="I will inspect.",
        ),
    )
    assert event.model_dump(mode="json")["payload"] == {
        "total_tokens": 1000,
        "text": "I will inspect.",
    }


def test_runtime_event_store_roundtrips_final_assistant_message_context(tmp_path) -> None:
    db_path = tmp_path / "runtime-final-assistant-message-context.db"
    run_store = SqliteStateStore(str(db_path))
    runtime_event_store = SqliteRuntimeEventStore(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_id = "550e8400-e29b-41d4-a716-446655440034"
    run_store.create_run(
        "internal",
        "skill",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=run_id,
    )

    runtime_event_store.append_event(
        RuntimeEventDraft(
            run_id=run_id,
            type=RuntimeEventType.AGENT_FINAL_ASSISTANT_MESSAGE,
            payload=AgentEventPayload(
                step_id="support_agent",
                turn_id="turn-4",
                agent_sequence=7,
                body=AgentBodyFinalMessage(
                    text="Done.",
                    context=AgentAssistantMessageContext(
                        compaction_enabled=False,
                        max_window_ratio=0.8,
                        max_window_tokens=100_000,
                        total_tokens=2144,
                        model="MiniMax-M2.5",
                    ),
                ),
            ),
        )
    )

    event = runtime_event_store.get_last_event(run_id)

    assert event is not None
    assert event.type == RuntimeEventType.AGENT_FINAL_ASSISTANT_MESSAGE
    assert event.payload == AgentEventPayload(
        step_id="support_agent",
        turn_id="turn-4",
        agent_sequence=7,
        body=AgentBodyFinalMessage(
            text="Done.",
            context=AgentAssistantMessageContext(
                compaction_enabled=False,
                max_window_ratio=0.8,
                max_window_tokens=100_000,
                total_tokens=2144,
                model="MiniMax-M2.5",
            ),
        ),
    )
    assert event.model_dump(mode="json")["payload"] == {
        "text": "Done.",
        "context": {
            "compaction_enabled": False,
            "max_window_ratio": 0.8,
            "max_window_tokens": 100_000,
            "total_tokens": 2144,
            "model": "MiniMax-M2.5",
        },
    }
