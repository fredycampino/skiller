from skiller.application.ports.run_store_port import RunStorePort
from skiller.application.use_cases.render_current_step import CurrentStep
from skiller.application.use_cases.step_execution_result import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.run_model import RunStatus
from skiller.domain.step_execution_model import NotifyOutput, StepExecution


class ExecuteNotifyStepUseCase:
    def __init__(self, store: RunStorePort) -> None:
        self.store = store

    def execute(self, next_step: CurrentStep) -> StepAdvance:
        step_id = next_step.step_id
        step = next_step.step
        context = next_step.context

        message = str(step.get("message", ""))
        execution = StepExecution(
            step_type=next_step.step_type,
            input={"message": message},
            evaluation={},
            output=NotifyOutput(text=message, message=message),
        )
        context.step_executions[step_id] = execution

        raw_next = step.get("next")
        if raw_next is None:
            self.store.update_run(
                next_step.run_id,
                status=RunStatus.RUNNING,
                context=context,
            )
            return StepAdvance(
                status=StepExecutionStatus.COMPLETED,
                execution=execution,
            )

        next_step_id = str(raw_next).strip()
        if not next_step_id:
            raise ValueError(f"Step '{step_id}' requires non-empty next")

        self.store.update_run(
            next_step.run_id,
            status=RunStatus.RUNNING,
            current=next_step_id,
            context=context,
        )
        return StepAdvance(
            status=StepExecutionStatus.NEXT,
            next_step_id=next_step_id,
            execution=execution,
        )
