import pytest

from skiller.domain.agent.agent_llm_provider_model import AgentCodexLLMModel, AgentLLMProviderType
from skiller.domain.agent.agent_run_model import AgentStopReason
from skiller.domain.step.step_execution_model import (
    AgentFinalOutputData,
    AgentOutput,
    AgentStopOutputData,
    AgentUsageOutput,
    StepExecution,
)
from skiller.domain.step.step_type import StepType

pytestmark = pytest.mark.unit


def test_agent_final_output_serializes_and_restores_typed_data() -> None:
    execution = StepExecution(
        step_type=StepType.AGENT,
        output=AgentOutput(
            text="Done.",
            text_ref="data.final",
            data=AgentFinalOutputData(
                stop_reason=AgentStopReason.FINAL,
                context_id="ctx-1",
                final="Done.",
                turn_count=2,
                tool_call_count=1,
                usage=AgentUsageOutput(
                    prompt_tokens=100,
                    completion_tokens=25,
                    total_tokens=125,
                    provider=AgentLLMProviderType.CODEX,
                    model=AgentCodexLLMModel.GPT_5_5,
                ),
            ),
        ),
    )

    persisted = execution.to_persisted_dict()

    assert persisted["output"] == {
        "text": "Done.",
        "text_ref": "data.final",
        "body_ref": None,
        "value": {
            "data": {
                "stop_reason": "final",
                "context_id": "ctx-1",
                "final": "Done.",
                "turn_count": 2,
                "tool_call_count": 1,
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 25,
                    "total_tokens": 125,
                    "provider": "codex",
                    "model": "gpt-5.5",
                },
            }
        },
    }
    assert StepExecution.from_dict(persisted) == execution


def test_agent_stop_output_serializes_and_restores_typed_data() -> None:
    execution = StepExecution(
        step_type=StepType.AGENT,
        output=AgentOutput(
            text="Agent stopped after reaching max turns.",
            text_ref="data.message",
            data=AgentStopOutputData(
                stop_reason=AgentStopReason.MAX_TURNS_EXHAUSTED,
                context_id="ctx-1",
                message="Agent stopped after reaching max turns.",
                turn_count=10,
                tool_call_count=5,
            ),
        ),
    )

    persisted = execution.to_persisted_dict()

    assert persisted["output"] == {
        "text": "Agent stopped after reaching max turns.",
        "text_ref": "data.message",
        "body_ref": None,
        "value": {
            "data": {
                "stop_reason": "max_turns_exhausted",
                "context_id": "ctx-1",
                "message": "Agent stopped after reaching max turns.",
                "turn_count": 10,
                "tool_call_count": 5,
            }
        },
    }
    assert StepExecution.from_dict(persisted) == execution


def test_agent_output_requires_data_when_restoring() -> None:
    with pytest.raises(ValueError, match="agent output data must be an object"):
        StepExecution.from_dict(
            {
                "step_type": "agent",
                "output": {
                    "text": "",
                    "value": {},
                },
            }
        )
