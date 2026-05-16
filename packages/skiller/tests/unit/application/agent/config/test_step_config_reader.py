import pytest
from helpers.agent_config import FakeAgentConfigPort, agent_config

from skiller.application.agent.config.step_config_reader import (
    AGENT_RUNTIME_SYSTEM,
    AgentStepConfigReader,
)
from skiller.domain.step.run_step_model import AgentStep

pytestmark = pytest.mark.unit


def test_agent_step_config_reader_reads_valid_step() -> None:
    reader = AgentStepConfigReader(
        agent_config=FakeAgentConfigPort(
            agent_config(
                max_turns=10,
                max_tool_calls=5,
            )
        )
    )

    config = reader.read(
        run_id="run-1",
        step=AgentStep(
            id="support_agent",
            system="Be useful.",
            task="Help user",
            context_id="thread-1",
            max_turns=3,
            max_tool_calls=2,
            tools=("notify", "shell"),
        ),
    )

    assert config.system == f"{AGENT_RUNTIME_SYSTEM}\n\nBe useful."
    assert config.task == "Help user"
    assert config.context_id == "thread-1"
    assert config.config.loop.max_turns == 3
    assert config.config.loop.max_tool_calls == 2
    assert config.tools == ("notify", "shell")


def test_agent_step_config_reader_uses_agent_config_loop_defaults() -> None:
    reader = AgentStepConfigReader(
        agent_config=FakeAgentConfigPort(
            agent_config(
                max_turns=10,
                max_tool_calls=5,
            )
        )
    )

    config = reader.read(
        run_id="run-1",
        step=AgentStep(
            id="support_agent",
            system="Be useful.",
            task="Help user",
            tools=(),
        ),
    )

    assert config.context_id == "run-1"
    assert config.config.loop.max_turns == 10
    assert config.config.loop.max_tool_calls == 5
    assert config.tools == ()
    assert config.system == f"{AGENT_RUNTIME_SYSTEM}\n\nBe useful."


def test_agent_step_config_reader_applies_step_overrides_without_mutating_base_config() -> None:
    base_config = agent_config(
        max_turns=10,
        max_tool_calls=5,
    )
    reader = AgentStepConfigReader(agent_config=FakeAgentConfigPort(base_config))

    config = reader.read(
        run_id="run-1",
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


def test_agent_step_config_reader_validates_contract() -> None:
    reader = AgentStepConfigReader(agent_config=FakeAgentConfigPort())

    with pytest.raises(ValueError, match="requires non-empty context_id"):
        reader.read(
            run_id="",
            step=AgentStep(
                id="support_agent",
                system="Be useful.",
                task="Help user",
                tools=(),
            ),
        )
