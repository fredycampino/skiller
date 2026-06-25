from skiller.application.agent.agent_runner import AgentRunner
from skiller.application.agent.config.agent_step_mapper import AgentStepMapper
from skiller.application.agent.config.step_config_reader import AgentStepConfigReader
from skiller.application.agent.mapper.agent_step_execution_mapper import (
    AgentStepExecutionMapper,
)
from skiller.application.agent.runner_state import AgentRunnerRequest
from skiller.domain.agent.run.identity import AgentRun
from skiller.domain.agent.run.model import AgentStopReason
from skiller.domain.run.run_model import RunStatus
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.step.current_step_model import CurrentStep
from skiller.domain.step.step_execution_model import (
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
        execution_mapper: AgentStepExecutionMapper,
    ) -> None:
        self.store = store
        self.runner = runner
        self.step_mapper = step_mapper
        self.config_reader = config_reader
        self.execution_mapper = execution_mapper

    def execute(self, current_step: CurrentStep) -> StepAdvance:
        step_id = current_step.step_id
        agent_step = self.step_mapper.to_agent(current_step)
        validation = self.config_reader.validate_agent_config(current_step=current_step)
        if not validation.ok:
            execution = self.execution_mapper.config_fail(
                current_step=current_step,
                agent_step=agent_step,
                validation=validation,
            )
            return self._advance(current_step=current_step, execution=execution)

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
        if runner_result.finish == AgentStopReason.LLM_REQUEST_FAILED:
            execution = self.execution_mapper.request_fail(
                current_step=current_step,
                config=config,
                runner_result=runner_result,
            )
            return self._advance(current_step=current_step, execution=execution)

        if runner_result.finish in {
            AgentStopReason.TOOL_EXECUTION_FAILED,
            AgentStopReason.INVALID_FINAL_MESSAGE,
        }:
            raise ValueError(runner_result.error or f"Agent step '{step_id}' failed")

        execution = self.execution_mapper.success(
            current_step=current_step,
            config=config,
            runner_result=runner_result,
        )
        return self._advance(current_step=current_step, execution=execution)

    def _advance(self, *, current_step: CurrentStep, execution: StepExecution) -> StepAdvance:
        step_id = current_step.step_id
        current_step.context.step_executions[step_id] = execution
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
