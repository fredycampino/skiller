from typing import Any

from skiller.application.ports.state_store_port import StateStorePort
from skiller.application.use_cases.render_current_step import CurrentStep
from skiller.application.use_cases.step_execution_result import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.run_model import RunStatus
from skiller.domain.step_execution_model import AssignOutput, StepExecution


class ExecuteAssignStepUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, current_step: CurrentStep) -> StepAdvance:
        step_id = current_step.step_id
        step = current_step.step
        values = step.get("values")

        if not isinstance(values, dict):
            raise ValueError(f"Step '{step_id}' requires values object")
        if not values:
            raise ValueError(f"Step '{step_id}' requires non-empty values object")

        assigned = self._clone(values)
        execution = StepExecution(
            step_type=current_step.step_type,
            input={"values": self._clone(values)},
            evaluation={},
            output=AssignOutput(text="Values assigned.", assigned=assigned),
        )
        current_step.context.step_executions[step_id] = execution

        raw_next = step.get("next")
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

    def _clone(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._clone(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._clone(item) for item in value]
        return value
