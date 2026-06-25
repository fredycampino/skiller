import pytest

from skiller.domain.action.action_model import OpenUrlAction, RunAction
from skiller.domain.agent.llm.provider_lmstudio import AgentLMStudioLLMModel
from skiller.domain.agent.llm.provider_registry import AgentCodexLLMModel, AgentLLMProviderType
from skiller.domain.agent.run.model import AgentStopReason
from skiller.domain.step.step_execution_model import (
    AgentFinalOutputData,
    AgentOutput,
    AgentStopOutputData,
    AgentUsageOutput,
    NotifyOutput,
    StepExecution,
)
from skiller.domain.step.step_type import StepType

pytestmark = pytest.mark.unit


def test_notify_open_url_action_serializes_and_restores_typed_data() -> None:
    execution = StepExecution(
        step_type=StepType.NOTIFY,
        output=NotifyOutput(
            text="Authorize the app",
            message="Authorize the app",
            action=OpenUrlAction(
                uid="action-open-url-1",
                label="Open authorization",
                message="Continue in the browser.",
                url="https://example.com/oauth/start",
                auto=True,
            ),
        ),
    )

    persisted = execution.to_persisted_dict()

    assert persisted["output"] == {
        "text": "Authorize the app",
        "body_ref": None,
        "value": {
            "message": "Authorize the app",
            "format": "simple",
                "action": {
                    "uid": "action-open-url-1",
                    "type": "open_url",
                    "label": "Open authorization",
                "message": "Continue in the browser.",
                "url": "https://example.com/oauth/start",
                "auto": True,
            },
        },
    }
    assert StepExecution.from_dict(persisted) == execution


def test_notify_run_action_serializes_and_restores_typed_data() -> None:
    execution = StepExecution(
        step_type=StepType.NOTIFY,
        output=NotifyOutput(
            text="Debug failure",
            message="Debug failure",
            action=RunAction(
                uid="action-run-1",
                label="Debug failure",
                arg="--file ./flows/debug.yaml",
                params="--mood nice --path .",
                auto=True,
            ),
        ),
    )

    persisted = execution.to_persisted_dict()

    assert persisted["output"] == {
        "text": "Debug failure",
        "body_ref": None,
        "value": {
            "message": "Debug failure",
            "format": "simple",
                "action": {
                    "uid": "action-run-1",
                    "type": "run",
                    "label": "Debug failure",
                "arg": "--file ./flows/debug.yaml",
                "params": "--mood nice --path .",
                "auto": True,
            },
        },
    }
    assert StepExecution.from_dict(persisted) == execution


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


def test_agent_final_output_restores_lmstudio_usage_model() -> None:
    persisted = {
        "step_type": "agent",
        "input": {},
        "evaluation": {},
        "output": {
            "text": "Done.",
            "text_ref": "data.final",
            "body_ref": None,
            "value": {
                "data": {
                    "stop_reason": "final",
                    "context_id": "ctx-1",
                    "final": "Done.",
                    "turn_count": 1,
                    "tool_call_count": 0,
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 25,
                        "total_tokens": 125,
                        "provider": "lmstudio",
                        "model": "google/gemma-4-12b-qat",
                    },
                }
            },
        },
    }

    execution = StepExecution.from_dict(persisted)

    assert isinstance(execution.output, AgentOutput)
    assert isinstance(execution.output.data, AgentFinalOutputData)
    assert execution.output.data.usage == AgentUsageOutput(
        prompt_tokens=100,
        completion_tokens=25,
        total_tokens=125,
        provider=AgentLLMProviderType.LMSTUDIO,
        model=AgentLMStudioLLMModel.GEMMA_4_12B_QAT,
    )


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
