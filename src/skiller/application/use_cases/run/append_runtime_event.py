from dataclasses import dataclass
from enum import Enum
from typing import Any

from skiller.application.ports.runtime_event_store_port import RuntimeEventStorePort
from skiller.domain.step.step_execution_model import StepExecution
from skiller.domain.step.step_type import StepType


class RuntimeEventType(str, Enum):
    RUN_CREATE = "RUN_CREATE"
    RUN_RESUME = "RUN_RESUME"
    STEP_STARTED = "STEP_STARTED"
    STEP_SUCCESS = "STEP_SUCCESS"
    STEP_ERROR = "STEP_ERROR"
    RUN_WAITING = "RUN_WAITING"
    RUN_FINISHED = "RUN_FINISHED"


@dataclass(frozen=True)
class AppendRuntimeEventResult:
    event_id: str


class AppendRuntimeEventUseCase:
    def __init__(self, store: RuntimeEventStorePort) -> None:
        self.store = store

    def execute(
        self,
        run_id: str,
        *,
        event_type: RuntimeEventType,
        payload: dict[str, Any] | None = None,
        step_id: str | None = None,
        step_type: StepType | None = None,
        execution: StepExecution | None = None,
        next_step_id: str | None = None,
        error: str | None = None,
    ) -> AppendRuntimeEventResult:
        event_payload = dict(payload or {})
        if step_id is not None:
            event_payload["step"] = step_id
        if step_type is not None:
            event_payload["step_type"] = step_type.value
        if execution is not None:
            event_payload["step_type"] = execution.step_type.value
            event_payload["output"] = execution.to_public_output_dict()
        if next_step_id is not None:
            event_payload["next"] = next_step_id
        if error is not None:
            event_payload["error"] = error
        event_id = self.store.append_event(event_type.value, event_payload, run_id=run_id)
        return AppendRuntimeEventResult(event_id=event_id)
