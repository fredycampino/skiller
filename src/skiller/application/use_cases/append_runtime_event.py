from dataclasses import dataclass
from enum import Enum
from typing import Any

from skiller.application.ports.state_store_port import StateStorePort


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
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(
        self,
        run_id: str,
        *,
        event_type: RuntimeEventType,
        payload: dict[str, Any],
    ) -> AppendRuntimeEventResult:
        event_id = self.store.append_event(event_type.value, payload, run_id=run_id)
        return AppendRuntimeEventResult(event_id=event_id)
