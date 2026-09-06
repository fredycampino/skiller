from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RunsPortItem:
    id: str
    flow_path: str
    status: str
    current: str | None
    created_at: str
    updated_at: str
    wait_type: str | None = None
    wait_detail: str | None = None


class RunsPort(Protocol):
    def list_runs(
        self,
        *,
        limit: int = 20,
        statuses: list[str] | None = None,
    ) -> list[RunsPortItem]: ...
