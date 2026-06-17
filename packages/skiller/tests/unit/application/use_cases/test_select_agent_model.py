from dataclasses import dataclass
from pathlib import Path

import pytest

from skiller.application.use_cases.agent.select_agent_model import (
    SelectAgentModelStatus,
    SelectAgentModelUseCase,
)
from skiller.domain.agent.agent_config_port import (
    AgentConfigProviderSource,
    AgentConfigProviderSourceItem,
)
from skiller.domain.agent.agent_llm_provider import AgentLLMProviderType
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run

pytestmark = pytest.mark.unit


def test_select_agent_model_updates_config_for_run(tmp_path: Path) -> None:
    config_path = tmp_path / "agent.json"
    config_path.write_text("{}", encoding="utf-8")
    agent_config = _FakeAgentConfig(
        sources=(
            AgentConfigProviderSourceItem(
                provider_type=AgentLLMProviderType.CODEX,
                source=AgentConfigProviderSource.GLOBAL,
            ),
        )
    )
    use_case = SelectAgentModelUseCase(
        run_store=_FakeRunStore(_build_run()),
        agent_config=agent_config,
        skill_runner=_FakeSkillRunner(config_path=config_path),
    )

    result = use_case.execute(
        run_id="run-1",
        provider="codex",
        model="gpt-5.4",
    )

    assert result.status == SelectAgentModelStatus.OK
    assert result.provider == "codex"
    assert result.model == "gpt-5.4"
    assert agent_config.source_config_paths == [config_path]
    assert agent_config.set_model_calls == [
        _SetModelCall(
            provider_type=AgentLLMProviderType.CODEX,
            model="gpt-5.4",
            config_path=config_path,
        )
    ]


def test_select_agent_model_returns_run_not_found() -> None:
    agent_config = _FakeAgentConfig(sources=())
    use_case = SelectAgentModelUseCase(
        run_store=_FakeRunStore(None),
        agent_config=agent_config,
        skill_runner=_FakeSkillRunner(),
    )

    result = use_case.execute(
        run_id="missing-run",
        provider="codex",
        model="gpt-5.4",
    )

    assert result.status == SelectAgentModelStatus.RUN_NOT_FOUND
    assert result.error == "Run 'missing-run' not found"
    assert agent_config.set_model_calls == []


def test_select_agent_model_rejects_unconfigured_provider() -> None:
    agent_config = _FakeAgentConfig(sources=())
    use_case = SelectAgentModelUseCase(
        run_store=_FakeRunStore(_build_run()),
        agent_config=agent_config,
        skill_runner=_FakeSkillRunner(),
    )

    result = use_case.execute(
        run_id="run-1",
        provider="codex",
        model="gpt-5.4",
    )

    assert result.status == SelectAgentModelStatus.PROVIDER_NOT_CONFIGURED
    assert result.error == "LLM provider is not configured: codex"
    assert agent_config.source_config_paths == [None]
    assert agent_config.set_model_calls == []


def test_select_agent_model_rejects_unsupported_provider() -> None:
    agent_config = _FakeAgentConfig(sources=())
    use_case = SelectAgentModelUseCase(
        run_store=_FakeRunStore(_build_run()),
        agent_config=agent_config,
        skill_runner=_FakeSkillRunner(),
    )

    result = use_case.execute(
        run_id="run-1",
        provider="unknown",
        model="model-1",
    )

    assert result.status == SelectAgentModelStatus.PROVIDER_NOT_SUPPORTED
    assert result.error == "Unsupported LLM provider: unknown"
    assert agent_config.source_config_paths == []
    assert agent_config.set_model_calls == []


def test_select_agent_model_rejects_unsupported_model() -> None:
    agent_config = _FakeAgentConfig(
        sources=(
            AgentConfigProviderSourceItem(
                provider_type=AgentLLMProviderType.CODEX,
                source=AgentConfigProviderSource.GLOBAL,
            ),
        )
    )
    use_case = SelectAgentModelUseCase(
        run_store=_FakeRunStore(_build_run()),
        agent_config=agent_config,
        skill_runner=_FakeSkillRunner(),
    )

    result = use_case.execute(
        run_id="run-1",
        provider="codex",
        model="not-a-codex-model",
    )

    assert result.status == SelectAgentModelStatus.MODEL_NOT_SUPPORTED
    assert result.error == "Unsupported model='not-a-codex-model' for provider='codex'"
    assert agent_config.source_config_paths == []
    assert agent_config.set_model_calls == []


@dataclass(frozen=True)
class _SetModelCall:
    provider_type: AgentLLMProviderType
    model: str
    config_path: Path | None


class _FakeRunStore:
    def __init__(self, run: Run | None) -> None:
        self.run = run

    def get_run(self, run_id: str) -> Run | None:
        _ = run_id
        return self.run


class _FakeAgentConfig:
    def __init__(
        self,
        *,
        sources: tuple[AgentConfigProviderSourceItem, ...],
    ) -> None:
        self.sources = sources
        self.source_config_paths: list[Path | None] = []
        self.set_model_calls: list[_SetModelCall] = []

    def list_provider_sources(
        self,
        *,
        config_path: Path | None = None,
    ) -> tuple[AgentConfigProviderSourceItem, ...]:
        self.source_config_paths.append(config_path)
        return self.sources

    def set_model(
        self,
        *,
        provider_type: AgentLLMProviderType,
        model: str,
        config_path: Path | None = None,
    ) -> None:
        self.set_model_calls.append(
            _SetModelCall(
                provider_type=provider_type,
                model=model,
                config_path=config_path,
            )
        )


class _FakeSkillRunner:
    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path

    def resolve_file_path(self, source: str, ref: str, file_ref: str) -> Path:
        _ = source, ref, file_ref
        if self.config_path is None:
            raise FileNotFoundError
        return self.config_path


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
