from typing import Any

from skiller.application.ports.state_store_port import StateStorePort
from skiller.application.use_cases.render_current_step import CurrentStep
from skiller.application.use_cases.step_execution_result import StepExecutionResult, StepExecutionStatus
from skiller.domain.run_model import RunStatus


class ExecuteSwitchStepUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, current_step: CurrentStep) -> StepExecutionResult:
        step = current_step.step
        step_id = current_step.step_id

        if "value" not in step:
            raise ValueError(f"Step '{step_id}' requires value")

        raw_cases = step.get("cases")
        if not isinstance(raw_cases, dict):
            raise ValueError(f"Step '{step_id}' requires cases object")
        if not raw_cases:
            raise ValueError(f"Step '{step_id}' requires non-empty cases object")

        raw_default = step.get("default")
        if raw_default is None:
            raise ValueError(f"Step '{step_id}' requires default")

        next_step_id = self._resolve_next_step_id(
            step_id=step_id,
            value=step["value"],
            raw_cases=raw_cases,
            raw_default=raw_default,
        )

        result = {
            "value": self._clone(step["value"]),
            "next": next_step_id,
        }
        current_step.context.results[step_id] = result

        self.store.append_event(
            "SWITCH_DECISION",
            {
                "step": step_id,
                "value": result["value"],
                "next": next_step_id,
            },
            run_id=current_step.run_id,
        )
        self.store.update_run(
            current_step.run_id,
            status=RunStatus.RUNNING,
            current=next_step_id,
            context=current_step.context,
        )
        return StepExecutionResult(
            status=StepExecutionStatus.NEXT,
            next_step_id=next_step_id,
        )

    def _resolve_next_step_id(
        self,
        *,
        step_id: str,
        value: Any,
        raw_cases: dict[object, object],
        raw_default: object,
    ) -> str:
        for raw_case_value, raw_next in raw_cases.items():
            if raw_case_value != value:
                continue
            return self._normalize_next_step_id(step_id=step_id, raw_next=raw_next, field="cases")

        return self._normalize_next_step_id(step_id=step_id, raw_next=raw_default, field="default")

    def _normalize_next_step_id(self, *, step_id: str, raw_next: object, field: str) -> str:
        next_step_id = str(raw_next).strip()
        if not next_step_id:
            raise ValueError(f"Step '{step_id}' requires non-empty {field} target")
        return next_step_id

    def _clone(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._clone(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._clone(item) for item in value]
        return value
