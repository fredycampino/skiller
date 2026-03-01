from typing import Any
import uuid

from runtime.application.ports.state_store import StateStorePort
from runtime.domain.models import Event


class StartRunUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, skill_name: str, inputs: dict[str, Any]) -> tuple[str, Event]:
        run_id = self.store.create_run(skill_name, {"inputs": inputs, "steps": {}})
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type="START_RUN",
            payload={"skill": skill_name, "inputs": inputs},
            run_id=run_id,
        )
        return run_id, event
