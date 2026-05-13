from dataclasses import dataclass

from skiller.domain.event.event_model import (
    RuntimeEventDraft,
    RuntimeEventPayload,
    RuntimeEventType,
)
from skiller.domain.event.runtime_event_store_port import RuntimeEventStorePort


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
        payload: RuntimeEventPayload,
        step_id: str | None = None,
        step_type: str | None = None,
        agent_sequence: int | None = None,
    ) -> AppendRuntimeEventResult:
        event_id = self.store.append_event(
            RuntimeEventDraft(
                run_id=run_id,
                type=event_type,
                payload=payload,
                step_id=step_id,
                step_type=step_type,
                agent_sequence=agent_sequence,
            )
        )
        return AppendRuntimeEventResult(event_id=event_id)
