from dataclasses import dataclass

from skiller.domain.event.event_model import RuntimeEventType
from skiller.domain.run.run_model import RunStatus


@dataclass(frozen=True, kw_only=True)
class RunStatusRuntime:
    run_id: str
    status: RunStatus
    wait_type: str = "none"
    prompt: str = ""
    last_event_sequence: int | None = None
    last_event_type: RuntimeEventType | None = None
