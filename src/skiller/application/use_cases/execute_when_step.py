from typing import Any

from skiller.application.ports.state_store_port import StateStorePort
from skiller.application.use_cases.render_current_step import CurrentStep
from skiller.application.use_cases.step_execution_result import StepExecutionResult, StepExecutionStatus
from skiller.domain.run_model import RunStatus

_SUPPORTED_WHEN_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte"}


class ExecuteWhenStepUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, current_step: CurrentStep) -> StepExecutionResult:
        step = current_step.step
        step_id = current_step.step_id

        if "value" not in step:
            raise ValueError(f"Step '{step_id}' requires value")

        raw_branches = step.get("branches")
        if not isinstance(raw_branches, list):
            raise ValueError(f"Step '{step_id}' requires branches list")
        if not raw_branches:
            raise ValueError(f"Step '{step_id}' requires non-empty branches list")

        raw_default = step.get("default")
        if raw_default is None:
            raise ValueError(f"Step '{step_id}' requires default")

        value = step["value"]
        next_step_id, decision = self._resolve_next_step_id(
            step_id=step_id,
            value=value,
            raw_branches=raw_branches,
            raw_default=raw_default,
        )

        result = {
            "value": self._clone(value),
            "next": next_step_id,
        }
        current_step.context.results[step_id] = result

        self.store.append_event(
            "WHEN_DECISION",
            {
                "step": step_id,
                "value": result["value"],
                "next": next_step_id,
                "branch": decision["branch"],
                "op": decision["op"],
                "right": decision["right"],
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
        raw_branches: list[object],
        raw_default: object,
    ) -> tuple[str, dict[str, Any]]:
        for index, raw_branch in enumerate(raw_branches):
            operator, right, next_step_id = self._parse_branch(step_id=step_id, index=index, raw_branch=raw_branch)
            if self._matches(step_id=step_id, value=value, operator=operator, right=right):
                return next_step_id, {
                    "branch": index,
                    "op": operator,
                    "right": self._clone(right),
                }

        return self._normalize_next_step_id(step_id=step_id, raw_next=raw_default, field="default"), {
            "branch": None,
            "op": None,
            "right": None,
        }

    def _parse_branch(
        self,
        *,
        step_id: str,
        index: int,
        raw_branch: object,
    ) -> tuple[str, Any, str]:
        if not isinstance(raw_branch, dict):
            raise ValueError(f"Step '{step_id}' requires branch {index} object")

        raw_then = raw_branch.get("then")
        if raw_then is None:
            raise ValueError(f"Step '{step_id}' requires branch {index} then")

        next_step_id = str(raw_then).strip()
        if not next_step_id:
            raise ValueError(f"Step '{step_id}' requires non-empty branch {index} then")

        operator_keys = [str(key).strip() for key in raw_branch.keys() if str(key).strip() != "then"]
        if len(operator_keys) != 1:
            raise ValueError(f"Step '{step_id}' requires exactly one operator in branch {index}")

        operator = operator_keys[0]
        if operator not in _SUPPORTED_WHEN_OPERATORS:
            raise ValueError(f"Step '{step_id}' uses unsupported when operator '{operator}' in branch {index}")

        return operator, raw_branch[operator], next_step_id

    def _matches(self, *, step_id: str, value: Any, operator: str, right: Any) -> bool:
        if operator == "eq":
            return value == right
        if operator == "ne":
            return value != right

        left_number = self._as_number(step_id=step_id, operator=operator, value=value)
        right_number = self._as_number(step_id=step_id, operator=operator, value=right)

        if operator == "gt":
            return left_number > right_number
        if operator == "gte":
            return left_number >= right_number
        if operator == "lt":
            return left_number < right_number
        return left_number <= right_number

    def _as_number(self, *, step_id: str, operator: str, value: Any) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Step '{step_id}' requires numeric operands for operator '{operator}'")
        return float(value)

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
