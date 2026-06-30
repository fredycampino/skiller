from dataclasses import dataclass
from pathlib import Path

import pytest

from skiller.application.use_cases.agent.select_agent_model import (
    SelectAgentModelStatus,
    SelectAgentModelUseCase,
)
from skiller.domain.agent.config.model import (
    AgentConfig,
    AgentContextCompactionConfig,
    AgentContextConfig,
    AgentEventOutputConfig,
    AgentEventOutputTruncateConfig,
    AgentLoopConfig,
)
from skiller.domain.agent.llm.model import AgentLLMProviderType, LLMCustomModel
from skiller.domain.agent.llm.provider_registry import (
    CODEX_MODELS,
    FAKE_MODELS,
    AgentCodexLLMModel,
    AgentCodexProvider,
    AgentFakeLLMModel,
    AgentFakeProvider,
    AgentLLMProviderList,
    AgentLMStudioProvider,
)
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run

pytestmark = pytest.mark.unit


def test_select_agent_model_updates_config_for_run(tmp_path: Path) -> None:
    config_path = tmp_path / "agent.json"
    config_path.write_text("{}", encoding="utf-8")
    agent_config = _FakeAgentConfig(
        config=_agent_config(_codex_provider())
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
    assert agent_config.set_model_calls == [
        _SetModelCall(
            provider_type=AgentLLMProviderType.CODEX,
            model="gpt-5.4",
            config_path=config_path,
        )
    ]


def test_select_agent_model_supports_lmstudio(tmp_path: Path) -> None:
    config_path = tmp_path / "agent.json"
    config_path.write_text("{}", encoding="utf-8")
    agent_config = _FakeAgentConfig(
        config=_agent_config(_lmstudio_provider())
    )
    use_case = SelectAgentModelUseCase(
        run_store=_FakeRunStore(_build_run()),
        agent_config=agent_config,
        skill_runner=_FakeSkillRunner(config_path=config_path),
    )

    result = use_case.execute(
        run_id="run-1",
        provider="lmstudio",
        model="google/gemma-4-12b-qat",
    )

    assert result.status == SelectAgentModelStatus.OK
    assert result.provider == "lmstudio"
    assert result.model == "google/gemma-4-12b-qat"
    assert agent_config.set_model_calls == [
        _SetModelCall(
            provider_type=AgentLLMProviderType.LMSTUDIO,
            model="google/gemma-4-12b-qat",
            config_path=config_path,
        )
    ]


def test_select_agent_model_supports_lmstudio_custom_model() -> None:
    custom_model = LLMCustomModel(
        value="local/gemma-custom",
        model_context_window_tokens=10_000,
    )
    agent_config = _FakeAgentConfig(
        config=_agent_config(
            AgentLMStudioProvider(
                model=custom_model,
                models=(custom_model,),
                timeout_seconds=30,
                window_width_tokens=10_000,
            )
        )
    )
    use_case = SelectAgentModelUseCase(
        run_store=_FakeRunStore(_build_run()),
        agent_config=agent_config,
        skill_runner=_FakeSkillRunner(),
    )

    result = use_case.execute(
        run_id="run-1",
        provider="lmstudio",
        model="local/gemma-custom",
    )

    assert result.status == SelectAgentModelStatus.OK
    assert agent_config.set_model_calls == [
        _SetModelCall(
            provider_type=AgentLLMProviderType.LMSTUDIO,
            model="local/gemma-custom",
            config_path=None,
        )
    ]


def test_select_agent_model_returns_run_not_found() -> None:
    agent_config = _FakeAgentConfig(config=_agent_config(_codex_provider()))
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
    agent_config = _FakeAgentConfig(config=_agent_config(_fake_provider()))
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
    assert agent_config.set_model_calls == []


def test_select_agent_model_rejects_unsupported_provider() -> None:
    agent_config = _FakeAgentConfig(config=_agent_config(_fake_provider()))
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
    assert agent_config.set_model_calls == []


def test_select_agent_model_rejects_unsupported_model() -> None:
    agent_config = _FakeAgentConfig(config=_agent_config(_codex_provider()))
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
        config: AgentConfig,
    ) -> None:
        self.config = config
        self.set_model_calls: list[_SetModelCall] = []

    def get_config(self, *, config_path: Path | None = None) -> AgentConfig:
        _ = config_path
        return self.config

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


def _agent_config(
    *providers: AgentCodexProvider | AgentLMStudioProvider | AgentFakeProvider,
) -> AgentConfig:
    if not providers:
        providers = (_fake_provider(),)
    return AgentConfig(
        llm=AgentLLMProviderList(
            default_provider=providers[0].type,
            providers=providers,
        ),
        loop=AgentLoopConfig(max_turns=2, max_tool_calls=3),
        context=AgentContextConfig(
            compaction=AgentContextCompactionConfig(
                enabled=False,
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
    )


def _codex_provider() -> AgentCodexProvider:
    return AgentCodexProvider(
        model=AgentCodexLLMModel.GPT_5_5,
        models=CODEX_MODELS,
        credentials_file="/tmp/openai-codex.json",
        timeout_seconds=120,
        window_width_tokens=1_050_000,
    )


def _lmstudio_model() -> LLMCustomModel:
    return LLMCustomModel(
        value="google/gemma-4-12b-qat",
        model_context_window_tokens=131_072,
    )


def _lmstudio_provider() -> AgentLMStudioProvider:
    return AgentLMStudioProvider(
        model=_lmstudio_model(),
        models=(_lmstudio_model(),),
        timeout_seconds=30,
        window_width_tokens=131_072,
    )


def _fake_provider() -> AgentFakeProvider:
    return AgentFakeProvider(
        model=AgentFakeLLMModel.MODEL1,
        models=FAKE_MODELS,
        timeout_seconds=30,
        window_width_tokens=100_000,
    )
