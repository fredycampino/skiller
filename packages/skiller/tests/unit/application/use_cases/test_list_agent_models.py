from pathlib import Path

import pytest

from skiller.application.use_cases.agent.list_agent_models import (
    ListAgentModelsStatus,
    ListAgentModelsUseCase,
)
from skiller.domain.agent.agent_config_model import (
    AgentConfig,
    AgentContextCompactionConfig,
    AgentContextConfig,
    AgentEventOutputConfig,
    AgentEventOutputTruncateConfig,
    AgentLoopConfig,
)
from skiller.domain.agent.agent_config_port import (
    AgentConfigProviderSource,
    AgentConfigProviderSourceItem,
)
from skiller.domain.agent.agent_llm_provider import AgentLLMProviderType
from skiller.domain.agent.agent_llm_provider_model import (
    AgentCodexLLMModel,
    AgentCodexProvider,
    AgentLLMProviderList,
    AgentMiniMaxLLMModel,
    AgentMiniMaxProvider,
)
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run

pytestmark = pytest.mark.unit


def test_list_agent_models_returns_configured_and_active_model() -> None:
    agent_config = _FakeAgentConfig(
        _agent_config(
            default_provider=AgentLLMProviderType.CODEX,
            providers=(
                AgentCodexProvider(
                    model=AgentCodexLLMModel.GPT_5_5,
                    timeout_seconds=120,
                    window_width_tokens=1050000,
                    credentials_file="/secret/codex.json",
                ),
                AgentMiniMaxProvider(
                    model=AgentMiniMaxLLMModel.M2_7,
                    timeout_seconds=30,
                    window_width_tokens=204800,
                    api_key="secret",
                ),
            ),
        )
    )
    use_case = ListAgentModelsUseCase(
        run_store=_FakeRunStore(_build_run()),
        agent_config=agent_config,
        skill_runner=_FakeSkillRunner(),
    )

    result = use_case.execute("run-1")

    assert result.status == ListAgentModelsStatus.OK
    codex = _provider(result.providers, "codex")
    minimax = _provider(result.providers, "minimax")
    bedrock = _provider(result.providers, "bedrock")
    provider_names = [provider.name for provider in result.providers]
    assert provider_names == ["minimax", "codex", "bedrock"]
    assert codex.source == AgentConfigProviderSource.GLOBAL
    assert minimax.source == AgentConfigProviderSource.GLOBAL
    assert bedrock.source == AgentConfigProviderSource.NONE
    assert _model(codex.models, "gpt-5.5").active is True
    assert _model(codex.models, "gpt-5.4").active is False
    assert _model(minimax.models, "MiniMax-M2.7").active is False
    assert agent_config.config_paths == [None]


def test_list_agent_models_returns_run_not_found() -> None:
    result = ListAgentModelsUseCase(
        run_store=_FakeRunStore(None),
        agent_config=_FakeAgentConfig(_codex_config()),
        skill_runner=_FakeSkillRunner(),
    ).execute("missing-run")

    assert result.status == ListAgentModelsStatus.RUN_NOT_FOUND
    assert result.providers == ()
    assert result.error == "Run 'missing-run' not found"


def test_list_agent_models_uses_resolved_run_agent_config_path(tmp_path: Path) -> None:
    config_path = tmp_path / "agent.json"
    config_path.write_text("{}", encoding="utf-8")
    agent_config = _FakeAgentConfig(_codex_config())
    use_case = ListAgentModelsUseCase(
        run_store=_FakeRunStore(_build_run()),
        agent_config=agent_config,
        skill_runner=_FakeSkillRunner(config_path=config_path),
    )

    result = use_case.execute("run-1")

    assert result.status == ListAgentModelsStatus.OK
    assert agent_config.config_paths == [config_path]
    assert agent_config.source_config_paths == [config_path]


class _FakeRunStore:
    def __init__(self, run: Run | None) -> None:
        self.run = run

    def get_run(self, run_id: str) -> Run | None:
        _ = run_id
        return self.run


class _FakeAgentConfig:
    def __init__(
        self,
        config: AgentConfig,
        sources: tuple[AgentConfigProviderSourceItem, ...] | None = None,
    ) -> None:
        self.config = config
        self.sources = sources
        self.config_paths: list[Path | None] = []
        self.source_config_paths: list[Path | None] = []

    def get_config(self, *, config_path: Path | None = None) -> AgentConfig:
        self.config_paths.append(config_path)
        return self.config

    def list_provider_sources(
        self,
        *,
        config_path: Path | None = None,
    ) -> tuple[AgentConfigProviderSourceItem, ...]:
        self.source_config_paths.append(config_path)
        if self.sources is not None:
            return self.sources
        return tuple(
            AgentConfigProviderSourceItem(
                provider_type=provider.type,
                source=AgentConfigProviderSource.GLOBAL,
            )
            for provider in self.config.llm.providers
        )


class _FakeSkillRunner:
    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path

    def resolve_file_path(self, source: str, ref: str, file_ref: str) -> Path:
        _ = source, ref, file_ref
        if self.config_path is None:
            raise FileNotFoundError
        return self.config_path


def _codex_config() -> AgentConfig:
    provider = AgentCodexProvider(
        model=AgentCodexLLMModel.GPT_5_5,
        timeout_seconds=120,
        window_width_tokens=1050000,
        credentials_file="/secret/codex.json",
    )
    return _agent_config(
        default_provider=AgentLLMProviderType.CODEX,
        providers=(provider,),
    )


def _agent_config(
    *,
    default_provider: AgentLLMProviderType,
    providers: tuple[AgentCodexProvider | AgentMiniMaxProvider, ...],
) -> AgentConfig:
    return AgentConfig(
        llm=AgentLLMProviderList(
            default_provider=default_provider,
            providers=providers,
        ),
        loop=AgentLoopConfig(
            max_turns=2,
            max_tool_calls=3,
        ),
        context=AgentContextConfig(
            compaction=AgentContextCompactionConfig(
                enabled=False,
                max_total_tokens_ratio=0.8,
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


def _provider(providers, name: str):  # noqa: ANN001, ANN202
    for provider in providers:
        if provider.name == name:
            return provider
    raise AssertionError(f"Missing provider {name}")


def _model(models, name: str):  # noqa: ANN001, ANN202
    for model in models:
        if model.name == name:
            return model
    raise AssertionError(f"Missing model {name}")
