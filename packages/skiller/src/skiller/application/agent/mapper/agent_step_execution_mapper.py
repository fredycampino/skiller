from skiller.application.agent.config.step_config_reader import AgentRunnerConfig
from skiller.application.agent.runner_state import AgentRunnerResult
from skiller.domain.agent.agent_config_validation_model import AgentConfigValidation
from skiller.domain.agent.agent_run_model import AgentStopReason
from skiller.domain.agent.llm_model import LLMUsage
from skiller.domain.step.current_step_model import CurrentStep
from skiller.domain.step.run_step_model import AgentStep
from skiller.domain.step.step_execution_model import (
    AgentFinalOutputData,
    AgentOutput,
    AgentStopOutputData,
    AgentUsageOutput,
    StepExecution,
)


class AgentStepExecutionMapper:
    def config_fail(
        self,
        *,
        current_step: CurrentStep,
        agent_step: AgentStep,
        validation: AgentConfigValidation,
    ) -> StepExecution:
        message = validation.message
        if validation.error is not None:
            message = f"{validation.message} ({validation.error.value})"

        return StepExecution(
            step_type=current_step.step_type,
            input={
                "system": agent_step.system,
                "task": agent_step.task,
                "tools": list(agent_step.tools),
            },
            output=AgentOutput(
                text=validation.message,
                text_ref="data.message",
                data=AgentStopOutputData(
                    stop_reason=AgentStopReason.CONFIG_INVALID,
                    context_id="",
                    message=message,
                    turn_count=0,
                    tool_call_count=0,
                ),
            ),
        )

    def request_fail(
        self,
        *,
        current_step: CurrentStep,
        config: AgentRunnerConfig,
        runner_result: AgentRunnerResult,
    ) -> StepExecution:
        message = runner_result.error or _stop_message(runner_result.finish)
        return StepExecution(
            step_type=current_step.step_type,
            input=_runner_input(config=config, runner_result=runner_result),
            output=AgentOutput(
                text=message,
                text_ref="data.message",
                data=AgentStopOutputData(
                    stop_reason=runner_result.finish,
                    context_id=runner_result.context_id,
                    message=message,
                    turn_count=runner_result.turn_count,
                    tool_call_count=runner_result.tool_call_count,
                ),
            ),
        )

    def success(
        self,
        *,
        current_step: CurrentStep,
        config: AgentRunnerConfig,
        runner_result: AgentRunnerResult,
    ) -> StepExecution:
        response_model = (
            runner_result.response_model.value
            if runner_result.response_model is not None
            else None
        )
        return StepExecution(
            step_type=current_step.step_type,
            input=_runner_input(config=config, runner_result=runner_result),
            evaluation={"model": response_model},
            output=_agent_output(
                context_id=runner_result.context_id,
                final_text=runner_result.final_text,
                turn_count=runner_result.turn_count,
                tool_call_count=runner_result.tool_call_count,
                stop_reason=runner_result.finish,
                usage=runner_result.usage,
            ),
        )


def _runner_input(
    *,
    config: AgentRunnerConfig,
    runner_result: AgentRunnerResult,
) -> dict[str, object]:
    return {
        "system": config.system,
        "task": config.task,
        "context_id": runner_result.context_id,
        "max_turns": config.config.loop.max_turns,
        "max_tool_calls": config.config.loop.max_tool_calls,
        "tools": [tool.name for tool in config.tools],
    }


def _agent_output(
    *,
    context_id: str,
    final_text: str | None,
    turn_count: int,
    tool_call_count: int,
    stop_reason: AgentStopReason,
    usage: LLMUsage | None,
) -> AgentOutput:
    if final_text is None:
        return AgentOutput(
            text="",
            data=AgentStopOutputData(
                stop_reason=stop_reason,
                context_id=context_id,
                message=_stop_message(stop_reason),
                turn_count=turn_count,
                tool_call_count=tool_call_count,
            ),
        )

    return AgentOutput(
        text=final_text,
        text_ref="data.final",
        data=AgentFinalOutputData(
            stop_reason=stop_reason,
            context_id=context_id,
            final=final_text,
            turn_count=turn_count,
            tool_call_count=tool_call_count,
            usage=_usage_output(usage) if usage is not None else None,
        ),
    )


def _stop_message(stop_reason: AgentStopReason) -> str:
    if stop_reason == AgentStopReason.INTERRUPTED:
        return "Agent execution interrupted."
    if stop_reason == AgentStopReason.MAX_TURNS_EXHAUSTED:
        return "Agent stopped after reaching max turns."
    return f"Agent stopped: {stop_reason.value}"


def _usage_output(usage: LLMUsage) -> AgentUsageOutput:
    return AgentUsageOutput(
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        provider=usage.provider,
        model=usage.model,
    )
