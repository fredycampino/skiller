from pathlib import Path

import pytest
from helpers.agent_config import FakeAgentConfigPort, agent_config

from skiller.application.agent.config.step_config_reader import AgentStepConfigReader
from skiller.application.agent.tools.tool_manager import ToolManager
from skiller.application.tools.notify import NotifyTool
from skiller.application.tools.shell import ShellProcessTool
from skiller.domain.agent.agent_config_validation_model import (
    AgentConfigValidation,
    AgentConfigValidationErrorCode,
)
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run, RunStatus
from skiller.domain.step.current_step_model import CurrentStep
from skiller.domain.step.run_step_model import AgentStep
from skiller.domain.step.step_type import StepType
from skiller.domain.tool.tool_contract import ToolDefinition

pytestmark = pytest.mark.unit


def test_agent_step_config_reader_reads_valid_step() -> None:
    notify_tool = NotifyTool()
    shell_tool = ShellProcessTool()
    reader = AgentStepConfigReader(
        agent_config=FakeAgentConfigPort(
            agent_config(
                max_turns=10,
                max_tool_calls=5,
            )
        ),
        run_store=_FakeRunStore(),
        skill_runner=_FakeSkillRunner(),
        tool_manager=_FakeToolManager(definitions=(notify_tool, shell_tool)),
    )

    config = reader.read(
        current_step=_current_step(),
        step=AgentStep(
            id="support_agent",
            system="Be useful.",
            task="Help user",
            max_turns=3,
            max_tool_calls=2,
            tools=("notify", "shell"),
        ),
    )

    assert "## Available Tools" in config.system
    assert "**notify**" in config.system
    assert "**shell**" in config.system
    assert "Be useful." in config.system
    assert config.task == "Help user"
    assert config.config.loop.max_turns == 3
    assert config.config.loop.max_tool_calls == 2
    assert config.tools == (notify_tool, shell_tool)


def test_agent_step_config_reader_reads_base_limits_without_tools() -> None:
    reader = AgentStepConfigReader(
        agent_config=FakeAgentConfigPort(
            agent_config(
                max_turns=10,
                max_tool_calls=5,
            )
        ),
        run_store=_FakeRunStore(),
        skill_runner=_FakeSkillRunner(),
        tool_manager=ToolManager(tools=[]),
    )

    config = reader.read(
        current_step=_current_step(),
        step=AgentStep(
            id="support_agent",
            system="Be useful.",
            task="Help user",
            tools=(),
        ),
    )

    assert config.config.loop.max_turns == 10
    assert config.config.loop.max_tool_calls == 5
    assert config.tools == ()
    assert "Be useful." in config.system
    assert "## Available Tools" not in config.system


def test_agent_step_config_reader_applies_step_overrides_without_mutating_base_config() -> None:
    base_config = agent_config(
        max_turns=10,
        max_tool_calls=5,
    )
    reader = AgentStepConfigReader(
        agent_config=FakeAgentConfigPort(base_config),
        run_store=_FakeRunStore(),
        skill_runner=_FakeSkillRunner(),
        tool_manager=ToolManager(tools=[]),
    )

    config = reader.read(
        current_step=_current_step(),
        step=AgentStep(
            id="support_agent",
            system="Be useful.",
            task="Help user",
            max_turns=2,
            max_tool_calls=3,
            tools=(),
        ),
    )

    assert config.config.loop.max_turns == 2
    assert config.config.loop.max_tool_calls == 3
    assert base_config.loop.max_turns == 10
    assert base_config.loop.max_tool_calls == 5
    assert config.config.llm.default_provider == base_config.llm.default_provider
    assert config.config.context.compaction == base_config.context.compaction
    assert config.config.event_output.truncate == base_config.event_output.truncate


def test_agent_step_config_reader_validates_agent_config_through_port() -> None:
    validation = AgentConfigValidation.invalid(
        error=AgentConfigValidationErrorCode.PROVIDER_MODEL_UNSUPPORTED,
        message="bad model",
    )
    agent_cfg = _FakeAgentConfigPort(validation=validation)
    reader = AgentStepConfigReader(
        agent_config=agent_cfg,
        run_store=_FakeRunStore(),
        skill_runner=_FakeSkillRunner(),
        tool_manager=ToolManager(tools=[]),
    )

    result = reader.validate_agent_config(current_step=_current_step())

    assert result == validation
    assert agent_cfg.validate_calls == 1


def test_agent_step_config_reader_uses_agent_json_next_to_skill_yaml(tmp_path) -> None:
    config_path = tmp_path / "agent.json"
    config_path.write_text("{}", encoding="utf-8")
    agent_cfg = FakeAgentConfigPort()
    skill_runner = _FakeSkillRunner(config_path=config_path)
    reader = AgentStepConfigReader(
        agent_config=agent_cfg,
        run_store=_FakeRunStore(source="internal", ref="mono"),
        skill_runner=skill_runner,
        tool_manager=ToolManager(tools=[]),
    )

    reader.read(
        current_step=_current_step(),
        step=AgentStep(
            id="support_agent",
            system="Be useful.",
            task="Help user",
            tools=(),
        ),
    )

    assert agent_cfg.config_paths == [config_path]
    assert skill_runner.calls == [("internal", "mono", "agent.json")]


def test_agent_step_config_reader_builds_tools_section_with_params() -> None:
    reader = AgentStepConfigReader(
        agent_config=FakeAgentConfigPort(
            agent_config(max_turns=10, max_tool_calls=5),
        ),
        run_store=_FakeRunStore(),
        skill_runner=_FakeSkillRunner(),
        tool_manager=_FakeToolManager(definitions=(NotifyTool(), ShellProcessTool())),
    )

    tools = reader.tool_manager.get_tool_definitions(["notify", "shell"])
    section = reader._build_tools_section(tools)

    assert section.startswith("## Available Tools")
    assert "**notify**" in section
    assert "**shell**" in section
    assert "Parameters: message" in section
    assert "Parameters: command" in section


def test_agent_step_config_reader_builds_tools_section_empty_when_no_tools() -> None:
    reader = AgentStepConfigReader(
        agent_config=FakeAgentConfigPort(
            agent_config(max_turns=10, max_tool_calls=5),
        ),
        run_store=_FakeRunStore(),
        skill_runner=_FakeSkillRunner(),
        tool_manager=ToolManager(tools=[]),
    )

    section = reader._build_tools_section([])

    assert section == ""


def _current_step() -> CurrentStep:
    return CurrentStep(
        run_id="run-1",
        step_index=0,
        step_id="support_agent",
        step_type=StepType.AGENT,
        step={"system": "Be useful.", "task": "Help user"},
        context=RunContext(inputs={}, step_executions={}),
    )


class _FakeRunStore:
    def __init__(self, *, source: str = "internal", ref: str = "demo") -> None:
        self.source = source
        self.ref = ref

    def get_run(self, run_id: str) -> Run:
        return Run(
            id=run_id,
            source=self.source,
            ref=self.ref,
            snapshot={"start": "support_agent", "steps": []},
            status=RunStatus.RUNNING.value,
            current="support_agent",
            context=RunContext(inputs={}, step_executions={}),
            created_at="2026-03-07 10:00:00",
            updated_at="2026-03-07 10:00:00",
        )


class _FakeToolManager:
    def __init__(self, *, definitions: tuple[ToolDefinition, ...]) -> None:
        self.definitions = definitions

    def get_tool_definitions(self, allowed_tools: list[str]) -> list[ToolDefinition]:
        return [
            definition
            for definition in self.definitions
            if definition.name in allowed_tools
        ]


class _FakeAgentConfigPort:
    def __init__(self, validation: AgentConfigValidation | None = None) -> None:
        self._validation = validation
        self.validate_calls = 0
        self.config_paths: list[Path] = []

    def get_config(self, *, config_path: Path | None = None) -> object:  # noqa: ANN201
        if config_path is not None:
            self.config_paths.append(config_path)
        raise AssertionError("get_config should not be called")

    def validate_config(
        self, *, config_path: Path | None = None
    ) -> AgentConfigValidation:
        _ = config_path
        self.validate_calls += 1
        return self._validation


class _FakeSkillRunner:
    def __init__(self, *, config_path: Path | None = None) -> None:
        self.config_path = config_path or Path("__missing__/agent.json")
        self.calls: list[tuple[str, str, str]] = []

    def resolve_file_path(
        self,
        source: str,
        ref: str,
        file_ref: str,
    ) -> Path:
        self.calls.append((source, ref, file_ref))
        return self.config_path
