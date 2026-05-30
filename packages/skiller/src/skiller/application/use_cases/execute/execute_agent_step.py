from skiller.application.agent.agent_runner import AgentRunner
from skiller.application.agent.config.agent_step_mapper import AgentStepMapper
from skiller.application.agent.config.step_config_reader import AgentStepConfigReader
from skiller.application.agent.runner_state import AgentRunnerRequest
from skiller.domain.agent.agent_config_validation_model import AgentConfigValidation
from skiller.domain.agent.agent_run_identity import AgentRun
from skiller.domain.agent.agent_run_model import AgentStopReason
from skiller.domain.agent.llm_model import LLMUsage
from skiller.domain.run.run_model import RunStatus
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.step.current_step_model import CurrentStep
from skiller.domain.step.run_step_model import AgentStep
from skiller.domain.step.step_execution_model import (
    AgentFinalOutputData,
    AgentOutput,
    AgentStopOutputData,
    AgentUsageOutput,
    StepExecution,
)
from skiller.domain.step.step_execution_result_model import (
    StepAdvance,
    StepExecutionStatus,
)


class ExecuteAgentStepUseCase:
    def __init__(
        self,
        store: RunStorePort,
        runner: AgentRunner,
        step_mapper: AgentStepMapper,
        config_reader: AgentStepConfigReader,
    ) -> None:
        self.store = store
        self.runner = runner
        self.step_mapper = step_mapper
        self.config_reader = config_reader

    def execute(self, current_step: CurrentStep) -> StepAdvance:
        step_id = current_step.step_id
        agent_step = self.step_mapper.to_agent(current_step)
        validation = self.config_reader.validate_agent_config(current_step=current_step)
        if not validation.ok:
            return self._advance_with_config_error(
                current_step=current_step,
                agent_step=agent_step,
                validation=validation,
                stop_reason=AgentStopReason.CONFIG_INVALID,
            )

        config = self.config_reader.read(
            step=agent_step,
            current_step=current_step,
        )
        agent = AgentRun(
            run_id=current_step.run_id,
            agent_id=step_id,
        )
        runner_result = self.runner.execute(
            AgentRunnerRequest(
                agent=agent,
                config=config,
            )
        )
        if runner_result.finish in {
            AgentStopReason.LLM_REQUEST_FAILED,
            AgentStopReason.TOOL_EXECUTION_FAILED,
            AgentStopReason.INVALID_FINAL_MESSAGE,
        }:
            raise ValueError(runner_result.error or f"Agent step '{step_id}' failed")

        response_model = (
            runner_result.response_model.value
            if runner_result.response_model is not None
            else None
        )
        output = _agent_output(
            context_id=runner_result.context_id,
            final_text=runner_result.final_text,
            turn_count=runner_result.turn_count,
            tool_call_count=runner_result.tool_call_count,
            stop_reason=runner_result.finish,
            usage=runner_result.usage,
        )
        execution = StepExecution(
            step_type=current_step.step_type,
            input={
                "system": config.system,
                "task": config.task,
                "context_id": runner_result.context_id,
                "max_turns": config.config.loop.max_turns,
                "max_tool_calls": config.config.loop.max_tool_calls,
                "tools": [tool.name for tool in config.tools],
            },
            evaluation={"model": response_model},
            output=output,
        )
        current_step.context.step_executions[step_id] = execution
        return self._advance(current_step=current_step, execution=execution)

    def _advance_with_config_error(
        self,
        *,
        current_step: CurrentStep,
        agent_step: AgentStep,
        validation: AgentConfigValidation,
        stop_reason: AgentStopReason,
    ) -> StepAdvance:
        message = validation.message
        if validation.error is not None:
            message = f"{validation.message} ({validation.error.value})"
        execution = StepExecution(
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
                    stop_reason=stop_reason,
                    context_id="",
                    message=message,
                    turn_count=0,
                    tool_call_count=0,
                ),
            ),
        )
        current_step.context.step_executions[current_step.step_id] = execution
        return self._advance(current_step=current_step, execution=execution)

    def _advance(self, *, current_step: CurrentStep, execution: StepExecution) -> StepAdvance:
        step_id = current_step.step_id
        raw_next = current_step.step.get("next")

        if raw_next is None:
            self.store.update_run(
                current_step.run_id,
                status=RunStatus.RUNNING,
                context=current_step.context,
            )
            return StepAdvance(
                status=StepExecutionStatus.COMPLETED,
                execution=execution,
            )

        next_step_id = str(raw_next).strip()
        if not next_step_id:
            raise ValueError(f"Step '{step_id}' requires non-empty next")

        self.store.update_run(
            current_step.run_id,
            status=RunStatus.RUNNING,
            current=next_step_id,
            context=current_step.context,
        )
        return StepAdvance(
            status=StepExecutionStatus.NEXT,
            next_step_id=next_step_id,
            execution=execution,
        )


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
