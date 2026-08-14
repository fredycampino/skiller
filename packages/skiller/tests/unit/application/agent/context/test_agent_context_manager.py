from dataclasses import replace

import pytest
from helpers.agent_config import agent_runner_config

from skiller.application.agent.context.agent_context_manager import AgentContextManager
from skiller.application.agent.prompt.prompt_builder import AgentPromptBuilder
from skiller.application.tools.notify import NotifyTool
from skiller.domain.agent.context.model import (
    AgentContextCompactionQuery,
    AgentContextEntry,
    AgentContextEntryType,
    AgentContextState,
    AgentContextWindowEntries,
    AgentContextWindowQuery,
    AgentUserMessagePayload,
)
from skiller.domain.agent.run.identity import AgentContext

pytestmark = pytest.mark.unit

NOTIFY_TOOL_DEFINITION = NotifyTool()



def test_agent_context_manager_build_context_recovers_initial_raw_window() -> None:
    entry = AgentContextEntry(
        id="entry-1",
        run_id="run-1",
        context_id="ctx-1",
        sequence=1,
        entry_type=AgentContextEntryType.USER_MESSAGE,
        payload=AgentUserMessagePayload(text="Raw task"),
        usage=None,
        source_step_id="agent-1",
        created_at="2026-05-16T00:00:00Z",
    )
    store = _FakeAgentContextStore(
        raw_windows=[
            AgentContextWindowEntries(entries=[entry], estimated_tokens=40_000)
        ],
    )
    state_store = _FakeAgentContextState()
    manager = AgentContextManager(
        agent_context_store=store,
        agent_context_state=state_store,
        prompt_builder=AgentPromptBuilder(),
    )
    context = AgentContext(
        run_id="run-1",
        agent_id="agent-1",
        context_id="ctx-1",
    )
    config = agent_runner_config(log_request_file=None)

    result = manager.build_context(context=context, config=config)

    assert store.raw_calls == [
        AgentContextWindowQuery(
            context_id="ctx-1",
            start_sequence=1,
            compacted_sequence=None,
        )
    ]
    assert store.compacted_calls == [
        AgentContextWindowQuery(
            context_id="ctx-1",
            start_sequence=1,
            compacted_sequence=None,
        )
    ]
    assert store.compaction_queries == []
    assert state_store.saved_states == []
    assert result.window_width_tokens == 100_000
    assert result.estimated_tokens == 40_000
    assert result.llm_request.messages[1].content == "Raw task"


def test_agent_context_manager_includes_resolved_system_in_compaction_condition() -> None:
    entry = AgentContextEntry(
        id="entry-1",
        run_id="run-1",
        context_id="ctx-1",
        sequence=1,
        entry_type=AgentContextEntryType.USER_MESSAGE,
        payload=AgentUserMessagePayload(text="Raw task"),
        usage=None,
        source_step_id="agent-1",
        created_at="2026-05-16T00:00:00Z",
    )
    compacted_state = AgentContextState(
        context_id="ctx-1",
        start_sequence=1,
        compacted_sequence=1,
        compaction_id=1,
    )
    store = _FakeAgentContextStore(
        raw_windows=[
            AgentContextWindowEntries(entries=[entry], estimated_tokens=79_999),
            AgentContextWindowEntries(entries=[], estimated_tokens=0),
        ],
        compacted_windows=[
            AgentContextWindowEntries(entries=[], estimated_tokens=0),
        ],
        selected_state=compacted_state,
    )
    state_store = _FakeAgentContextState()
    manager = AgentContextManager(
        agent_context_store=store,
        agent_context_state=state_store,
        prompt_builder=AgentPromptBuilder(),
    )
    context = AgentContext(
        run_id="run-1",
        agent_id="agent-1",
        context_id="ctx-1",
    )
    config = agent_runner_config(system="xxx", log_request_file=None)

    manager.build_context(context=context, config=config)

    assert store.compaction_queries == [
        AgentContextCompactionQuery(
            context_id="ctx-1",
            start_sequence=1,
            compacted_sequence=None,
            compaction_id=0,
            keep_last_blocks=5,
            target_tokens=50_000,
        )
    ]
    assert state_store.saved_states == [compacted_state]


def test_agent_context_manager_build_context_compacts_and_recovers_new_window() -> None:
    initial_entry = AgentContextEntry(
        id="entry-1",
        run_id="run-1",
        context_id="ctx-1",
        sequence=1,
        entry_type=AgentContextEntryType.USER_MESSAGE,
        payload=AgentUserMessagePayload(text="Initial task"),
        usage=None,
        source_step_id="agent-1",
        created_at="2026-05-16T00:00:00Z",
    )
    compacted_entry = replace(
        initial_entry,
        id="entry-3",
        sequence=3,
        payload=AgentUserMessagePayload(text="Compacted task"),
    )
    raw_entry = replace(
        initial_entry,
        id="entry-8",
        sequence=8,
        payload=AgentUserMessagePayload(text="Raw task"),
    )
    compacted_state = AgentContextState(
        context_id="ctx-1",
        start_sequence=3,
        compacted_sequence=7,
        compaction_id=1,
    )
    store = _FakeAgentContextStore(
        raw_windows=[
            AgentContextWindowEntries(entries=[initial_entry], estimated_tokens=80_000),
            AgentContextWindowEntries(entries=[raw_entry], estimated_tokens=30_000),
        ],
        compacted_windows=[
            AgentContextWindowEntries(entries=[compacted_entry], estimated_tokens=20_000)
        ],
        selected_state=compacted_state,
    )
    state_store = _FakeAgentContextState()
    manager = AgentContextManager(
        agent_context_store=store,
        agent_context_state=state_store,
        prompt_builder=AgentPromptBuilder(),
    )
    context = AgentContext(
        run_id="run-1",
        agent_id="agent-1",
        context_id="ctx-1",
    )
    config = agent_runner_config(log_request_file=None)

    result = manager.build_context(context=context, config=config)

    assert store.compaction_queries == [
        AgentContextCompactionQuery(
            context_id="ctx-1",
            start_sequence=1,
            compacted_sequence=None,
            compaction_id=0,
            keep_last_blocks=5,
            target_tokens=50_000,
        )
    ]
    assert state_store.saved_states == [compacted_state]
    assert store.compacted_calls == [
        AgentContextWindowQuery(
            context_id="ctx-1",
            start_sequence=1,
            compacted_sequence=None,
        ),
        AgentContextWindowQuery(
            context_id="ctx-1",
            start_sequence=3,
            compacted_sequence=7,
        )
    ]
    assert store.raw_calls == [
        AgentContextWindowQuery(
            context_id="ctx-1",
            start_sequence=1,
            compacted_sequence=None,
        ),
        AgentContextWindowQuery(
            context_id="ctx-1",
            start_sequence=3,
            compacted_sequence=7,
        ),
    ]
    assert result.estimated_tokens == 50_000
    assert [message.content for message in result.llm_request.messages] == [
        "Be useful.",
        "Compacted task",
        "Raw task",
    ]


def test_agent_context_manager_build_context_recovers_persisted_window_below_trigger() -> None:
    compacted_entry = AgentContextEntry(
        id="entry-3",
        run_id="run-1",
        context_id="ctx-1",
        sequence=3,
        entry_type=AgentContextEntryType.USER_MESSAGE,
        payload=AgentUserMessagePayload(text="Compacted task"),
        usage=None,
        source_step_id="agent-1",
        created_at="2026-05-16T00:00:00Z",
    )
    raw_entry = replace(
        compacted_entry,
        id="entry-8",
        sequence=8,
        payload=AgentUserMessagePayload(text="Raw task"),
    )
    persisted_state = AgentContextState(
        context_id="ctx-1",
        start_sequence=3,
        compacted_sequence=7,
        compaction_id=1,
    )
    store = _FakeAgentContextStore(
        raw_windows=[
            AgentContextWindowEntries(entries=[raw_entry], estimated_tokens=30_000)
        ],
        compacted_windows=[
            AgentContextWindowEntries(entries=[compacted_entry], estimated_tokens=20_000)
        ],
    )
    state_store = _FakeAgentContextState(state=persisted_state)
    manager = AgentContextManager(
        agent_context_store=store,
        agent_context_state=state_store,
        prompt_builder=AgentPromptBuilder(),
    )
    context = AgentContext(
        run_id="run-1",
        agent_id="agent-1",
        context_id="ctx-1",
    )
    config = agent_runner_config(log_request_file=None)

    result = manager.build_context(context=context, config=config)

    assert store.compaction_queries == []
    assert state_store.saved_states == []
    assert store.compacted_calls == [
        AgentContextWindowQuery(
            context_id="ctx-1",
            start_sequence=3,
            compacted_sequence=7,
        )
    ]
    assert store.raw_calls == [
        AgentContextWindowQuery(
            context_id="ctx-1",
            start_sequence=3,
            compacted_sequence=7,
        )
    ]
    assert result.estimated_tokens == 50_000


def test_agent_context_manager_build_context_stops_when_state_persistence_fails() -> None:
    entry = AgentContextEntry(
        id="entry-1",
        run_id="run-1",
        context_id="ctx-1",
        sequence=1,
        entry_type=AgentContextEntryType.USER_MESSAGE,
        payload=AgentUserMessagePayload(text="Raw task"),
        usage=None,
        source_step_id="agent-1",
        created_at="2026-05-16T00:00:00Z",
    )
    compacted_state = AgentContextState(
        context_id="ctx-1",
        start_sequence=3,
        compacted_sequence=7,
        compaction_id=1,
    )
    store = _FakeAgentContextStore(
        raw_windows=[
            AgentContextWindowEntries(entries=[entry], estimated_tokens=80_000)
        ],
        selected_state=compacted_state,
    )
    state_store = _FakeAgentContextState(save_error=RuntimeError("state write failed"))
    manager = AgentContextManager(
        agent_context_store=store,
        agent_context_state=state_store,
        prompt_builder=AgentPromptBuilder(),
    )
    context = AgentContext(
        run_id="run-1",
        agent_id="agent-1",
        context_id="ctx-1",
    )
    config = agent_runner_config(log_request_file=None)

    with pytest.raises(RuntimeError, match="state write failed"):
        manager.build_context(context=context, config=config)

    assert state_store.saved_states == []
    assert store.raw_calls == [
        AgentContextWindowQuery(
            context_id="ctx-1",
            start_sequence=1,
            compacted_sequence=None,
        )
    ]
    assert store.compacted_calls == [
        AgentContextWindowQuery(
            context_id="ctx-1",
            start_sequence=1,
            compacted_sequence=None,
        )
    ]


class _FakeAgentContextStore:
    def __init__(
        self,
        *,
        raw_windows: list[AgentContextWindowEntries] | None = None,
        compacted_windows: list[AgentContextWindowEntries] | None = None,
        selected_state: AgentContextState | None = None,
        next_turn_id: str = "turn-2",
    ) -> None:
        self.raw_windows = raw_windows or []
        self.compacted_windows = compacted_windows or []
        self.selected_state = selected_state
        self.next = next_turn_id
        self.raw_calls: list[AgentContextWindowQuery] = []
        self.compacted_calls: list[AgentContextWindowQuery] = []
        self.compaction_queries: list[AgentContextCompactionQuery] = []

    def append_user_message(self, **kwargs):  # noqa: ANN003, ANN201
        raise NotImplementedError

    def append_tool_calls_assistant_message(self, **kwargs):  # noqa: ANN003, ANN201
        raise NotImplementedError

    def append_final_assistant_message(self, **kwargs):  # noqa: ANN003, ANN201
        raise NotImplementedError

    def append_tool_call(self, **kwargs):  # noqa: ANN003, ANN201
        raise NotImplementedError

    def append_tool_result(self, **kwargs):  # noqa: ANN003, ANN201
        raise NotImplementedError

    def add_compact_delta_tokens(self, **kwargs):  # noqa: ANN003, ANN201
        raise NotImplementedError

    def list_entries(self, *, context_id: str) -> list[AgentContextEntry]:
        _ = context_id
        raise NotImplementedError

    def list_raw_entries(
        self,
        *,
        query: AgentContextWindowQuery,
    ) -> AgentContextWindowEntries:
        self.raw_calls.append(query)
        index = len(self.raw_calls) - 1
        return self.raw_windows[index]

    def list_compact_entries(
        self,
        *,
        query: AgentContextWindowQuery,
    ) -> AgentContextWindowEntries:
        self.compacted_calls.append(query)
        if query.compacted_sequence is None:
            return AgentContextWindowEntries(entries=[], estimated_tokens=0)
        if query.compacted_sequence < query.start_sequence:
            return AgentContextWindowEntries(entries=[], estimated_tokens=0)
        index = len(self.compacted_calls) - 1
        return self.compacted_windows[index - 1]

    def select_compaction_state(
        self,
        *,
        query: AgentContextCompactionQuery,
    ) -> AgentContextState:
        self.compaction_queries.append(query)
        assert self.selected_state is not None
        return self.selected_state

    def next_turn_id(self, *, context_id: str) -> str:
        _ = context_id
        return self.next

    def get_last_usage_marker(self, *, context_id: str):  # noqa: ANN201
        _ = context_id
        raise NotImplementedError


class _FakeAgentContextState:
    def __init__(
        self,
        *,
        state: AgentContextState | None = None,
        save_error: Exception | None = None,
    ) -> None:
        self.state = state
        self.save_error = save_error
        self.saved_states: list[AgentContextState] = []

    def get_state(self, *, context_id: str) -> AgentContextState:
        _ = context_id
        if self.state is not None:
            return self.state
        return AgentContextState(
            context_id=context_id,
            start_sequence=1,
            compacted_sequence=None,
            compaction_id=0,
        )

    def save_state(self, *, state: AgentContextState) -> None:
        if self.save_error is not None:
            raise self.save_error
        self.saved_states.append(state)
        self.state = state
