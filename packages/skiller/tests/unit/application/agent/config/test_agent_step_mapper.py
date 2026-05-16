import pytest

from skiller.application.agent.config.agent_step_mapper import AgentStepMapper
from skiller.application.use_cases.render.render_current_step import CurrentStep
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.step.step_type import StepType

pytestmark = pytest.mark.unit


def test_agent_step_mapper_maps_valid_agent_step() -> None:
    step = AgentStepMapper().to_agent(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="support_agent",
            step_type=StepType.AGENT,
            step={
                "system": "Be useful.",
                "task": "Help user",
                "context_id": "thread-1",
                "max_turns": 3,
                "max_tool_calls": 2,
                "tools": ["notify", "shell"],
                "next": "done",
            },
            context=RunContext(inputs={}, step_executions={}),
        )
    )

    assert step.id == "support_agent"
    assert step.system == "Be useful."
    assert step.task == "Help user"
    assert step.context_id == "thread-1"
    assert step.max_turns == 3
    assert step.max_tool_calls == 2
    assert step.tools == ("notify", "shell")
    assert step.next == "done"


@pytest.mark.parametrize(
    ("body", "expected"),
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
def test_agent_step_mapper_validates_agent_step_body(
    body: dict[str, object],
    expected: str,
) -> None:
    with pytest.raises(ValueError, match=expected):
        AgentStepMapper().to_agent(
            CurrentStep(
                run_id="run-1",
                step_index=0,
                step_id="support_agent",
                step_type=StepType.AGENT,
                step=body,
                context=RunContext(inputs={}, step_executions={}),
            )
        )


def test_agent_step_mapper_rejects_non_agent_step() -> None:
    with pytest.raises(ValueError, match="must be an agent step"):
        AgentStepMapper().to_agent(
            CurrentStep(
                run_id="run-1",
                step_index=0,
                step_id="notify_user",
                step_type=StepType.NOTIFY,
                step={"message": "hello"},
                context=RunContext(inputs={}, step_executions={}),
            )
        )
