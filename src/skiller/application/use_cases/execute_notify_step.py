from skiller.application.ports.state_store_port import StateStorePort
from skiller.application.use_cases.render_current_step import CurrentStep
from skiller.application.use_cases.step_execution_result import StepExecutionResult, StepExecutionStatus
from skiller.domain.run_model import RunStatus


class ExecuteNotifyStepUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, next_step: CurrentStep) -> StepExecutionResult:
        step_id = next_step.step_id
        step = next_step.step
        context = next_step.context

        message = str(step.get("message", ""))
        context.results[step_id] = {"ok": True, "message": message}
        self.store.append_event("NOTIFY", {"step": step_id, "message": message}, run_id=next_step.run_id)

        raw_next = step.get("next")
        if raw_next is None:
            self.store.update_run(
                next_step.run_id,
                status=RunStatus.RUNNING,
                context=context,
            )
            return StepExecutionResult(status=StepExecutionStatus.COMPLETED)

        next_step_id = str(raw_next).strip()
        if not next_step_id:
            raise ValueError(f"Step '{step_id}' requires non-empty next")

        self.store.update_run(
            next_step.run_id,
            status=RunStatus.RUNNING,
            current=next_step_id,
            context=context,
        )
        return StepExecutionResult(
            status=StepExecutionStatus.NEXT,
            next_step_id=next_step_id,
        )
