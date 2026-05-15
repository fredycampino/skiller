from skiller.application.agent.agent_runner import AgentRunner
from skiller.application.agent.config.step_config_reader import AgentStepConfigReader
from skiller.application.agent.runner_state import AgentRunnerRequest
from skiller.application.use_cases.render.render_current_step import CurrentStep
from skiller.application.use_cases.shared.step_execution_result import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.agent.agent_run_model import AgentRunnerFinish
from skiller.domain.run.run_model import RunStatus
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.step.step_execution_model import AgentOutput, StepExecution


class ExecuteAgentStepUseCase:
    def __init__(
        self,
        store: RunStorePort,
        runner: AgentRunner,
        config_reader: AgentStepConfigReader | None = None,
    ) -> None:
        self.store = store
        self.runner = runner
        self.config_reader = config_reader or AgentStepConfigReader()

    def execute(self, current_step: CurrentStep) -> StepAdvance:
        step_id = current_step.step_id
        config = self.config_reader.read(
            step_id=step_id,
            run_id=current_step.run_id,
            step=current_step.step,
        )
        runner_result = self.runner.execute(
            AgentRunnerRequest(
                run_id=current_step.run_id,
                step_id=step_id,
                config=config,
            )
        )
        if runner_result.finish in {
            AgentRunnerFinish.LLM_REQUEST_FAILED,
            AgentRunnerFinish.TOOL_EXECUTION_FAILED,
            AgentRunnerFinish.INVALID_FINAL_MESSAGE,
        }:
            raise ValueError(runner_result.error or f"Agent step '{step_id}' failed")

        final = (
            {"text": runner_result.final_text}
            if runner_result.final_text is not None
            else None
        )
        output_data = {
            "context_id": config.context_id,
            "final": final,
            "turn_count": runner_result.turn_count,
            "tool_call_count": runner_result.tool_call_count,
            "stop_reason": runner_result.finish.value,
        }
        execution = StepExecution(
            step_type=current_step.step_type,
            input={
                "system": config.system,
                "task": config.task,
                "context_id": config.context_id,
                "max_turns": config.max_turns,
                "max_tool_calls": config.max_tool_calls,
                "tools": list(config.tools),
            },
            evaluation={"model": runner_result.response_model},
            output=AgentOutput(
                text=runner_result.final_text or "",
                text_ref="data.final.text" if runner_result.final_text is not None else None,
                data=output_data,
            ),
        )
        current_step.context.step_executions[step_id] = execution
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
