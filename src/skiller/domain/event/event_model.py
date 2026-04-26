from dataclasses import dataclass
from typing import Any


@dataclass
class Event:
    event_id: str
    event_type: str
    payload: dict[str, Any]
    run_id: str | None = None
