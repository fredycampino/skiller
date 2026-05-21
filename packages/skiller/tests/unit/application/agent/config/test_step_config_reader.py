import pytest
from helpers.agent_config import FakeAgentConfigPort, agent_config

from skiller.application.agent.config.step_config_reader import (
    AGENT_RUNTIME_SYSTEM,
    AgentStepConfigReader,
)
from skiller.application.agent.tools.tool_manager import ToolManager
from skiller.domain.agent.agent_config_validation_model import (
    AgentConfigValidation,
    AgentConfigValidationErrorCode,
)
from skiller.domain.step.run_step_model import AgentStep
from skiller.domain.tool.tool_contract import ToolConfig

pytestmark = pytest.mark.unit


def test_agent_step_config_reader_reads_valid_step() -> None:
    notify_tool = ToolConfig(
        name="notify",
        description="Fake notify tool",
        parameters_schema={},
    )
    shell_tool = ToolConfig(
        name="shell",
        description="Fake shell tool",
        parameters_schema={},
    )
    reader = AgentStepConfigReader(
        agent_config=FakeAgentConfigPort(
            agent_config(
                max_turns=10,
                max_tool_calls=5,
            )
        ),
        tool_manager=_FakeToolManager(tools=(notify_tool, shell_tool)),
    )

    config = reader.read(
        step=AgentStep(
            id="support_agent",
            system="Be useful.",
            task="Help user",
            max_turns=3,
            max_tool_calls=2,
            tools=("notify", "shell"),
        ),
    )

    assert config.system == f"{AGENT_RUNTIME_SYSTEM}\n\nBe useful."
    assert config.task == "Help user"
    assert config.config.loop.max_turns == 3
    assert config.config.loop.max_tool_calls == 2
    assert config.tools == (notify_tool, shell_tool)


def test_agent_step_config_reader_reads_defaults_without_tools() -> None:
    reader = AgentStepConfigReader(
        agent_config=FakeAgentConfigPort(
            agent_config(
                max_turns=10,
                max_tool_calls=5,
            )
        ),
        tool_manager=ToolManager(tools=[]),
    )

    config = reader.read(
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
    assert config.system == f"{AGENT_RUNTIME_SYSTEM}\n\nBe useful."


def test_agent_step_config_reader_applies_step_overrides_without_mutating_base_config() -> None:
    base_config = agent_config(
        max_turns=10,
        max_tool_calls=5,
    )
    reader = AgentStepConfigReader(
        agent_config=FakeAgentConfigPort(base_config),
        tool_manager=ToolManager(tools=[]),
    )

    config = reader.read(
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
    agent_config = _FakeAgentConfigPort(validation=validation)
    reader = AgentStepConfigReader(
        agent_config=agent_config,
        tool_manager=ToolManager(tools=[]),
    )

    result = reader.validate_agent_config()

    assert result == validation
    assert agent_config.validate_calls == 1


class _FakeToolManager:
    def __init__(self, *, tools: tuple[ToolConfig, ...]) -> None:
        self.tools = tools

    def get_tool_configs(self, allowed_tools: list[str]) -> list[ToolConfig]:
        return [
            tool
            for tool in self.tools
            if tool.name in allowed_tools
        ]


class _FakeAgentConfigPort:
    def __init__(self, *, validation: AgentConfigValidation) -> None:
        self.validation = validation
        self.validate_calls = 0

    def get_config(self):  # noqa: ANN201
        raise AssertionError("get_config should not be called")

    def validate_config(self) -> AgentConfigValidation:
        self.validate_calls += 1
        return self.validation
