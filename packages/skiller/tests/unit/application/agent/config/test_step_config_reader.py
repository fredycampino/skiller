import pytest

from skiller.application.agent.config.step_config_reader import (
    AGENT_RUNTIME_SYSTEM,
    AgentStepConfigReader,
)

pytestmark = pytest.mark.unit


def test_agent_step_config_reader_reads_valid_step() -> None:
    reader = AgentStepConfigReader()

    config = reader.read(
        step_id="support_agent",
        run_id="run-1",
        step={
            "system": "Be useful.",
            "task": "Help user",
            "context_id": "thread-1",
            "max_turns": 3,
            "tools": ["notify", "shell"],
        },
    )

    assert config.system == f"{AGENT_RUNTIME_SYSTEM}\n\nBe useful."
    assert config.task == "Help user"
    assert config.context_id == "thread-1"
    assert config.max_turns == 3
    assert config.tools == ["notify", "shell"]


def test_agent_step_config_reader_uses_defaults() -> None:
    reader = AgentStepConfigReader()

    config = reader.read(
        step_id="support_agent",
        run_id="run-1",
        step={
            "system": "Be useful.",
            "task": "Help user",
        },
    )

    assert config.context_id == "run-1"
    assert config.max_turns == 1
    assert config.max_tool_calls == 1
    assert config.tools == []
    assert config.system == f"{AGENT_RUNTIME_SYSTEM}\n\nBe useful."


def test_agent_step_config_reader_uses_runtime_loop_defaults() -> None:
    reader = AgentStepConfigReader(
        default_max_turns=10,
        default_max_tool_calls=5,
    )

    config = reader.read(
        step_id="support_agent",
        run_id="run-1",
        step={
            "system": "Be useful.",
            "task": "Help user",
        },
    )

    assert config.max_turns == 10
    assert config.max_tool_calls == 5


def test_agent_step_config_reader_merges_runtime_system_with_step_system() -> None:
    reader = AgentStepConfigReader()

    config = reader.read(
        step_id="support_agent",
        run_id="run-1",
        step={
            "system": "Focus on git diagnostics.",
            "task": "Help user",
        },
    )

    assert config.system == (f"{AGENT_RUNTIME_SYSTEM}\n\nFocus on git diagnostics.")


@pytest.mark.parametrize(
    ("step", "expected"),
    [
        ({"task": "Help user"}, "requires system"),
        ({"system": "Be useful."}, "requires task"),
        (
            {"system": "Be useful.", "task": "x", "max_turns": "3"},
            "requires integer max_turns",
        ),
        (
            {"system": "Be useful.", "task": "x", "max_turns": 0},
            "requires positive max_turns",
        ),
        (
            {"system": "Be useful.", "task": "x", "tools": "notify"},
            "requires list tools",
        ),
        (
            {"system": "Be useful.", "task": "x", "tools": ["notify", ""]},
            "requires non-empty tool names",
        ),
        (
            {"system": {"file": "./system.md"}, "task": "x"},
            "requires string system",
        ),
        (
            {"system": "Be useful.", "task": {"file": "./task.md"}},
            "requires string task",
        ),
    ],
)
def test_agent_step_config_reader_validates_contract(
    step: dict[str, object],
    expected: str,
) -> None:
    reader = AgentStepConfigReader()

    with pytest.raises(ValueError, match=expected):
        reader.read(step_id="support_agent", run_id="run-1", step=step)
