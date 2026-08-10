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
    AgentContextWindowEntries,
    AgentToolResultPayload,
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
    context_store = _FakeAgentContextStore(
        entries=[
            _user_entry(1, "hello", compact=4),
            _assistant_entry(2, AgentAssistantMessageType.FINAL, "hi", delta=20, compact=5),
            _assistant_entry(3, AgentAssistantMessageType.TOOL_CALLS, "", delta=8),
            _tool_result_entry(4, "x" * 10),
        ],
    )
    use_case = ListAgentContextUseCase(
        run_store=_FakeRunStore(_build_run()),
        run_agent_store=_FakeRunAgentStore(RunAgent("support_agent", "ctx-1")),
        agent_context_store=context_store,
        agent_config=_FakeAgentConfig(_agent_config(compaction_enabled=True)),
        skill_runner=_FakeSkillRunner(),
    )

    result = use_case.execute("run-1", "support_agent")

    assert result.status == ListAgentContextStatus.OK
    assert result.context_id == "ctx-1"
    assert result.window is not None
    assert result.window.mode == "compact"
    assert result.window.entries == 4
    assert result.window.start_sequence == 1
    assert result.window.end_sequence == 4
    assert result.window.limit_tokens == 80000
    assert result.window.estimated_tokens == 33
    assert result.window.payload_bytes == sum(entry.payload_bytes for entry in result.entries)
    assert result.window.keep_last == 5
    assert context_store.compact_calls == [("ctx-1", 80000, 5)]
    assert context_store.window_calls == []
    assert [entry.role for entry in result.entries] == ["user", "assistant", "assistant", "tool"]
    assert [entry.type for entry in result.entries] == [
        "message",
        "final",
        "tool_calls",
        "tool_result",
    ]
    assert [entry.prunable for entry in result.entries] == [False, False, True, True]
    assert result.entries[0].delta_compact_tokens == 4
    assert result.entries[1].delta_tokens == 20
    assert result.entries[2].usage is True
    assert result.entries[3].payload_bytes > 10


def test_list_agent_context_uses_normal_window_when_compaction_is_disabled() -> None:
    context_store = _FakeAgentContextStore(entries=[_user_entry(3, "recent", compact=3)])
    result = ListAgentContextUseCase(
        run_store=_FakeRunStore(_build_run()),
        run_agent_store=_FakeRunAgentStore(RunAgent("support_agent", "ctx-1")),
        agent_context_store=context_store,
        agent_config=_FakeAgentConfig(_agent_config(compaction_enabled=False)),
        skill_runner=_FakeSkillRunner(),
    ).execute("run-1", "support_agent")

    assert result.status == ListAgentContextStatus.OK
    assert result.window is not None
    assert result.window.mode == "window"
    assert context_store.window_calls == [("ctx-1", 80000)]
    assert context_store.compact_calls == []


def test_list_agent_context_returns_not_found_statuses() -> None:
    missing_run = ListAgentContextUseCase(
        run_store=_FakeRunStore(None),
        run_agent_store=_FakeRunAgentStore(None),
        agent_context_store=_FakeAgentContextStore(entries=[]),
        agent_config=_FakeAgentConfig(),
        skill_runner=_FakeSkillRunner(),
    ).execute("missing-run", "support_agent")
    missing_agent = ListAgentContextUseCase(
        run_store=_FakeRunStore(_build_run()),
        run_agent_store=_FakeRunAgentStore(None),
        agent_context_store=_FakeAgentContextStore(entries=[]),
        agent_config=_FakeAgentConfig(),
        skill_runner=_FakeSkillRunner(),
    ).execute("run-1", "support_agent")
    no_context = ListAgentContextUseCase(
        run_store=_FakeRunStore(_build_run()),
        run_agent_store=_FakeRunAgentStore(RunAgent("support_agent", None)),
        agent_context_store=_FakeAgentContextStore(entries=[]),
        agent_config=_FakeAgentConfig(),
        skill_runner=_FakeSkillRunner(),
    ).execute("run-1", "support_agent")

    assert missing_run.status == ListAgentContextStatus.RUN_NOT_FOUND
    assert missing_agent.status == ListAgentContextStatus.AGENT_NOT_FOUND
    assert no_context.status == ListAgentContextStatus.AGENT_CONTEXT_NOT_READY


def test_list_agent_context_rejects_invalid_programmer_input() -> None:
    use_case = ListAgentContextUseCase(
        run_store=_FakeRunStore(_build_run()),
        run_agent_store=_FakeRunAgentStore(None),
        agent_context_store=_FakeAgentContextStore(entries=[]),
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
    def __init__(self, *, entries: list[AgentContextEntry]) -> None:
        self.entries = entries
        self.compact_calls: list[tuple[str, int, int]] = []
        self.window_calls: list[tuple[str, int]] = []

    def list_compact_entries(
        self,
        *,
        context_id: str,
        window_width_tokens: int,
        keep_last_blocks: int,
    ) -> AgentContextWindowEntries:
        self.compact_calls.append((context_id, window_width_tokens, keep_last_blocks))
        return AgentContextWindowEntries(entries=self.entries, estimated_tokens=33)

    def list_window_entries(
        self,
        *,
        context_id: str,
        window_width_tokens: int,
    ) -> AgentContextWindowEntries:
        self.window_calls.append((context_id, window_width_tokens))
        return AgentContextWindowEntries(entries=self.entries, estimated_tokens=7)


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
        window_start_sequence=1,
        window_base=False,
    )


def _tool_result_entry(sequence: int, value: str) -> AgentContextEntry:
    return AgentContextEntry(
        id=f"entry-{sequence}",
        run_id="run-1",
        context_id="ctx-1",
        sequence=sequence,
        entry_type=AgentContextEntryType.TOOL_RESULT,
        payload=AgentToolResultPayload(
            turn_id="turn-1",
            parent_sequence=3,
            tool_call_id="call-1",
            tool="shell",
            status="ok",
            data={"stdout": value},
            error=None,
        ),
        usage=None,
        source_step_id="support_agent",
        created_at="2026-05-16T00:00:00Z",
    )


def _agent_config(*, compaction_enabled: bool = False) -> AgentConfig:
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
                enabled=compaction_enabled,
                max_total_tokens_ratio=0.8,
                keep_last=5,
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
