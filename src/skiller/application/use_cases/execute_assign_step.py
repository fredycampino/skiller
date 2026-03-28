from typing import Any

from skiller.application.ports.state_store_port import StateStorePort
from skiller.application.use_cases.render_current_step import CurrentStep
from skiller.application.use_cases.step_execution_result import (
    AssignResult,
    StepExecutionResult,
    StepExecutionStatus,
)
from skiller.domain.run_model import RunStatus


class ExecuteAssignStepUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, current_step: CurrentStep) -> StepExecutionResult:
        step_id = current_step.step_id
        step = current_step.step
        values = step.get("values")

        if not isinstance(values, dict):
            raise ValueError(f"Step '{step_id}' requires values object")
        if not values:
            raise ValueError(f"Step '{step_id}' requires non-empty values object")

        result = self._clone(values)
        current_step.context.results[step_id] = result

        raw_next = step.get("next")
        if raw_next is None:
            self.store.update_run(
                current_step.run_id,
                status=RunStatus.RUNNING,
                context=current_step.context,
            )
            return StepExecutionResult(
                status=StepExecutionStatus.COMPLETED,
                result=AssignResult(value=result),
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
        return StepExecutionResult(
            status=StepExecutionStatus.NEXT,
            next_step_id=next_step_id,
            result=AssignResult(value=result),
        )

    def _clone(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._clone(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._clone(item) for item in value]
        return value
