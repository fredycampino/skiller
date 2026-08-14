import pytest

from skiller.application.use_cases.agent.list_agent_context import (
    ListAgentContextStatus,
    ListAgentContextUseCase,
)
from skiller.domain.agent.config.model import (
    AgentConfig,
    AgentContextCompactionConfig,
    AgentContextConfig,
    AgentDebugConfig,
    AgentEventOutputConfig,
    AgentEventOutputTruncateConfig,
    AgentLoopConfig,
)
from skiller.domain.agent.context.model import (
    AgentAssistantMessagePayload,
    AgentAssistantMessageType,
    AgentContextEntry,
    AgentContextEntryType,
    AgentContextState,
    AgentContextWindowEntries,
    AgentContextWindowQuery,
    AgentUserMessagePayload,
)
from skiller.domain.agent.llm.model import LLMUsage
from skiller.domain.agent.llm.provider_registry import (
    NULL_MODELS,
    AgentLLMProviderList,
    AgentLLMProviderType,
    AgentNullLLMModel,
    AgentNullProvider,
)
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run, RunAgent

pytestmark = pytest.mark.unit


def test_list_agent_context_uses_compact_window_and_returns_metadata_without_payload() -> None:
    compacted_entry = _user_entry(1, "hello", compact=4)
    raw_entry = _assistant_entry(2, AgentAssistantMessageType.FINAL, "hi", delta=20, compact=5)
    context_store = _FakeAgentContextStore(
        compacted_entries=AgentContextWindowEntries(entries=[compacted_entry], estimated_tokens=4),
        raw_entries=AgentContextWindowEntries(entries=[raw_entry], estimated_tokens=20),
    )
    state_store = _FakeAgentContextState(
        state=AgentContextState(
            context_id="ctx-1",
            start_sequence=1,
            compacted_sequence=1,
            compaction_id=1,
        )
    )
    use_case = ListAgentContextUseCase(
        run_store=_FakeRunStore(_build_run()),
        run_agent_store=_FakeRunAgentStore(RunAgent("support_agent", "ctx-1")),
        agent_context_store=context_store,
        agent_context_state=state_store,
        agent_config=_FakeAgentConfig(_agent_config()),
        skill_runner=_FakeSkillRunner(),
    )

    result = use_case.execute("run-1", "support_agent")

    assert result.status == ListAgentContextStatus.OK
    assert result.context_id == "ctx-1"
    assert result.window is not None
    assert result.window.mode == "compact"
    assert result.window.entries == 2
    assert result.window.start_sequence == 1
    assert result.window.end_sequence == 2
    assert result.window.estimated_tokens == 24
    assert result.window.keep_last == 5
    assert context_store.compact_queries == [
        AgentContextWindowQuery(context_id="ctx-1", start_sequence=1, compacted_sequence=1)
    ]
    assert context_store.raw_queries == [
        AgentContextWindowQuery(context_id="ctx-1", start_sequence=1, compacted_sequence=1)
    ]
    assert [entry.role for entry in result.entries] == ["user", "assistant"]
    assert [entry.type for entry in result.entries] == ["message", "final"]
    assert [entry.prunable for entry in result.entries] == [False, False]
    assert result.entries[0].delta_compact_tokens == 4
    assert result.entries[1].delta_tokens == 20


def test_list_agent_context_uses_raw_window_when_no_compaction_state() -> None:
    raw_entry = _user_entry(3, "recent", compact=3)
    context_store = _FakeAgentContextStore(
        compacted_entries=AgentContextWindowEntries(entries=[], estimated_tokens=0),
        raw_entries=AgentContextWindowEntries(entries=[raw_entry], estimated_tokens=3),
    )
    state_store = _FakeAgentContextState(
        state=AgentContextState(
            context_id="ctx-1",
            start_sequence=1,
            compacted_sequence=None,
            compaction_id=0,
        )
    )
    result = ListAgentContextUseCase(
        run_store=_FakeRunStore(_build_run()),
        run_agent_store=_FakeRunAgentStore(RunAgent("support_agent", "ctx-1")),
        agent_context_store=context_store,
        agent_context_state=state_store,
        agent_config=_FakeAgentConfig(_agent_config()),
        skill_runner=_FakeSkillRunner(),
    ).execute("run-1", "support_agent")

    assert result.status == ListAgentContextStatus.OK
    assert result.window is not None
    assert result.window.mode == "raw"
    assert result.window.entries == 1
    assert result.window.start_sequence == 1
    assert context_store.compact_queries == [
        AgentContextWindowQuery(context_id="ctx-1", start_sequence=1, compacted_sequence=None)
    ]
    assert context_store.raw_queries == [
        AgentContextWindowQuery(context_id="ctx-1", start_sequence=1, compacted_sequence=None)
    ]


def test_list_agent_context_returns_not_found_statuses() -> None:
    state_store = _FakeAgentContextState()
    context_store = _FakeAgentContextStore(
        compacted_entries=AgentContextWindowEntries(entries=[], estimated_tokens=0),
        raw_entries=AgentContextWindowEntries(entries=[], estimated_tokens=0),
    )

    missing_run = ListAgentContextUseCase(
        run_store=_FakeRunStore(None),
        run_agent_store=_FakeRunAgentStore(None),
        agent_context_store=context_store,
        agent_context_state=state_store,
        agent_config=_FakeAgentConfig(),
        skill_runner=_FakeSkillRunner(),
    ).execute("missing-run", "support_agent")
    missing_agent = ListAgentContextUseCase(
        run_store=_FakeRunStore(_build_run()),
        run_agent_store=_FakeRunAgentStore(None),
        agent_context_store=context_store,
        agent_context_state=state_store,
        agent_config=_FakeAgentConfig(),
        skill_runner=_FakeSkillRunner(),
    ).execute("run-1", "support_agent")
    no_context = ListAgentContextUseCase(
        run_store=_FakeRunStore(_build_run()),
        run_agent_store=_FakeRunAgentStore(RunAgent("support_agent", None)),
        agent_context_store=context_store,
        agent_context_state=state_store,
        agent_config=_FakeAgentConfig(),
        skill_runner=_FakeSkillRunner(),
    ).execute("run-1", "support_agent")

    assert missing_run.status == ListAgentContextStatus.RUN_NOT_FOUND
    assert missing_agent.status == ListAgentContextStatus.AGENT_NOT_FOUND
    assert no_context.status == ListAgentContextStatus.AGENT_CONTEXT_NOT_READY


def test_list_agent_context_rejects_invalid_programmer_input() -> None:
    state_store = _FakeAgentContextState()
    context_store = _FakeAgentContextStore(
        compacted_entries=AgentContextWindowEntries(entries=[], estimated_tokens=0),
        raw_entries=AgentContextWindowEntries(entries=[], estimated_tokens=0),
    )
    use_case = ListAgentContextUseCase(
        run_store=_FakeRunStore(_build_run()),
        run_agent_store=_FakeRunAgentStore(None),
        agent_context_store=context_store,
        agent_context_state=state_store,
        agent_config=_FakeAgentConfig(),
        skill_runner=_FakeSkillRunner(),
    )

    with pytest.raises(RuntimeError, match="requires run_id and agent_id"):
        use_case.execute("", "support_agent")

    with pytest.raises(RuntimeError, match="requires run_id and agent_id"):
        use_case.execute("run-1", "")


class _FakeRunStore:
    def __init__(self, run: Run | None) -> None:
        self.run = run

    def get_run(self, run_id: str) -> Run | None:
        _ = run_id
        return self.run


class _FakeRunAgentStore:
    def __init__(self, agent: RunAgent | None) -> None:
        self.agent = agent

    def get_agent(self, *, run_id: str, agent_id: str) -> RunAgent | None:
        _ = run_id, agent_id
        return self.agent


class _FakeAgentContextStore:
    def __init__(
        self,
        *,
        compacted_entries: AgentContextWindowEntries,
        raw_entries: AgentContextWindowEntries,
    ) -> None:
        self.compacted_entries = compacted_entries
        self.raw_entries = raw_entries
        self.compact_queries: list[AgentContextWindowQuery] = []
        self.raw_queries: list[AgentContextWindowQuery] = []

    def list_compact_entries(self, *, query: AgentContextWindowQuery) -> AgentContextWindowEntries:
        self.compact_queries.append(query)
        return self.compacted_entries

    def list_raw_entries(self, *, query: AgentContextWindowQuery) -> AgentContextWindowEntries:
        self.raw_queries.append(query)
        return self.raw_entries


class _FakeAgentContextState:
    def __init__(self, state: AgentContextState | None = None) -> None:
        self.state = state

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


class _FakeAgentConfig:
    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or _agent_config()

    def get_config(self, *, config_path=None) -> AgentConfig:  # noqa: ANN001
        _ = config_path
        return self.config


class _FakeSkillRunner:
    def resolve_file_path(self, source: str, ref: str, file_ref: str):  # noqa: ANN001
        _ = source, ref, file_ref
        raise FileNotFoundError


def _user_entry(sequence: int, text: str, *, compact: int) -> AgentContextEntry:
    return AgentContextEntry(
        id=f"entry-{sequence}",
        run_id="run-1",
        context_id="ctx-1",
        sequence=sequence,
        entry_type=AgentContextEntryType.USER_MESSAGE,
        payload=AgentUserMessagePayload(text=text),
        usage=None,
        source_step_id="support_agent",
        created_at="2026-05-16T00:00:00Z",
        delta_compact_tokens=compact,
    )


def _assistant_entry(
    sequence: int,
    message_type: AgentAssistantMessageType,
    text: str,
    *,
    delta: int,
    compact: int | None = None,
) -> AgentContextEntry:
    return AgentContextEntry(
        id=f"entry-{sequence}",
        run_id="run-1",
        context_id="ctx-1",
        sequence=sequence,
        entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
        message_type=message_type,
        payload=AgentAssistantMessagePayload(
            turn_id="turn-1",
            message_type=message_type,
            text=text,
        ),
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=50,
            output_tokens=2,
            total_tokens=52,
        ),
        source_step_id="support_agent",
        created_at="2026-05-16T00:00:00Z",
        delta_tokens=delta,
        delta_compact_tokens=compact,
        compaction_id=0,
    )


def _agent_config() -> AgentConfig:
    provider = AgentNullProvider(
        model=AgentNullLLMModel.NULL1,
        models=NULL_MODELS,
        timeout_seconds=30,
    )
    return AgentConfig(
        llm=AgentLLMProviderList(
            default_provider=AgentLLMProviderType.NULL,
            providers=(provider,),
        ),
        loop=AgentLoopConfig(max_turns=2, max_tool_calls=3),
        context=AgentContextConfig(
            window_width_tokens=100000,
            compaction=AgentContextCompactionConfig(
                compaction_trigger_ratio=0.8,
                compaction_target_ratio=0.5,
                keep_last_blocks=5,
            ),
        ),
        event_output=AgentEventOutputConfig(
            truncate=AgentEventOutputTruncateConfig(
                enabled=True,
                max_text_chars=100,
                max_json_chars=1000,
                max_array_items=10,
            ),
        ),
        debug=AgentDebugConfig(
            log_request=False,
            log_request_file=None,
            log_override_file=True,
        ),
    )


def _build_run() -> Run:
    return Run(
        id="run-1",
        source="internal",
        ref="demo",
        snapshot={"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        status="RUNNING",
        current="support_agent",
        context=RunContext(inputs={}, step_executions={}),
        created_at="2026-05-16T00:00:00Z",
        updated_at="2026-05-16T00:00:00Z",
    )
