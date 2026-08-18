from pathlib import Path

import pytest

from skiller.application.tools.files.config import FilesToolRuntimeConfig
from skiller.application.tools.files.tool import FilesTool
from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.application.tools.shell.process_tool import ShellProcessTool
from skiller.application.use_cases.agent.get_agent_tools import (
    GetAgentToolsStatus,
    GetAgentToolsUseCase,
)
from skiller.domain.agent.config.model import (
    AgentConfig,
    AgentContextCompactionConfig,
    AgentContextConfig,
    AgentDebugConfig,
    AgentEventOutputConfig,
    AgentEventOutputTruncateConfig,
    AgentLLMSelection,
    AgentLoopConfig,
)
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run, RunAgent
from skiller.domain.tool.tool_contract import ToolRuntimeConfigs

pytestmark = pytest.mark.unit


def test_get_agent_tools_returns_effective_tools_for_first_run_agent(tmp_path: Path) -> None:
    config_path = tmp_path / "agent.json"
    config_path.write_text("{}", encoding="utf-8")
    agent_config = _FakeAgentConfig(_agent_config())
    use_case = GetAgentToolsUseCase(
        run_store=_FakeRunStore(_build_run()),
        run_agent_store=_FakeRunAgentStore(RunAgent("support_agent", "context-1")),
        agent_config=agent_config,
        skill_runner=_FakeSkillRunner(config_path=config_path),
    )

    result = use_case.execute("run-1")

    assert result.status == GetAgentToolsStatus.OK
    assert result.run_id == "run-1"
    assert result.agent_id == "support_agent"
    assert result.source == "internal"
    assert result.ref == "demo"
    assert result.config_path == config_path
    assert result.tools is not None
    assert result.tools.shell.enabled is True
    assert result.tools.shell.allowed_paths == (Path("/workspace"),)
    assert result.tools.shell.allowed_commands == ("git", "pytest")
    assert result.tools.files.enabled is True
    assert result.tools.files.read == (Path("/workspace"),)
    assert result.tools.files.write == (Path("/workspace/src"),)
    assert agent_config.config_paths == [config_path]


def test_get_agent_tools_returns_run_not_found() -> None:
    result = GetAgentToolsUseCase(
        run_store=_FakeRunStore(None),
        run_agent_store=_FakeRunAgentStore(RunAgent("support_agent", "context-1")),
        agent_config=_FakeAgentConfig(_agent_config()),
        skill_runner=_FakeSkillRunner(),
    ).execute("missing-run")

    assert result.status == GetAgentToolsStatus.RUN_NOT_FOUND
    assert result.error == "Run 'missing-run' not found"
    assert result.tools is None


def test_get_agent_tools_returns_agent_not_found_when_run_has_no_agents() -> None:
    result = GetAgentToolsUseCase(
        run_store=_FakeRunStore(_build_run()),
        run_agent_store=_FakeRunAgentStore(None),
        agent_config=_FakeAgentConfig(_agent_config()),
        skill_runner=_FakeSkillRunner(),
    ).execute("run-1")

    assert result.status == GetAgentToolsStatus.AGENT_NOT_FOUND
    assert result.error == "Run 'run-1' has no attached agents"
    assert result.source == "internal"
    assert result.ref == "demo"
    assert result.tools is None


def test_get_agent_tools_rejects_invalid_programmer_input() -> None:
    use_case = GetAgentToolsUseCase(
        run_store=_FakeRunStore(_build_run()),
        run_agent_store=_FakeRunAgentStore(None),
        agent_config=_FakeAgentConfig(_agent_config()),
        skill_runner=_FakeSkillRunner(),
    )

    with pytest.raises(RuntimeError, match="requires run_id"):
        use_case.execute("")


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
        return self.agent if self.agent is not None and self.agent.agent_id == agent_id else None

    def get_first_agent(self, *, run_id: str) -> RunAgent | None:
        _ = run_id
        return self.agent


class _FakeAgentConfig:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.config_paths: list[Path | None] = []

    def get_config(self, *, config_path=None) -> AgentConfig:  # noqa: ANN001
        self.config_paths.append(config_path)
        return self.config


class _FakeSkillRunner:
    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path

    def resolve_file_path(self, source: str, ref: str, file_ref: str):  # noqa: ANN001
        _ = source, ref, file_ref
        if self.config_path is None:
            raise FileNotFoundError
        return self.config_path


def _agent_config() -> AgentConfig:
    return AgentConfig(
        llm=AgentLLMSelection(provider="null", model="null1"),
        loop=AgentLoopConfig(
            max_turns=2,
            max_tool_calls=3,
        ),
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
        tools=ToolRuntimeConfigs(
            items=(
                ShellToolRuntimeConfig(
                    definition=ShellProcessTool,
                    allowed_paths=(Path("/workspace"),),
                    allowlist_enabled=True,
                    allow_env_prefix=True,
                    allowed_commands=("git", "pytest"),
                ),
                FilesToolRuntimeConfig(
                    definition=FilesTool,
                    read=(Path("/workspace"),),
                    write=(Path("/workspace/src"),),
                    all=(),
                ),
            )
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
