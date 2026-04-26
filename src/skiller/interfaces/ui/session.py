from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


def build_session_key() -> str:
    return uuid.uuid4().hex[:8]


@dataclass
class UiRun:
    raw_args: str
    run_id: str | None = None
    status: str = "CREATED"
    error: str | None = None
    last_payload: dict[str, Any] = field(default_factory=dict)
    logs: list[dict[str, Any]] = field(default_factory=list)
    seen_event_ids: set[str] = field(default_factory=set)
    has_rendered_create_block: bool = False


@dataclass
class UiSession:
    session_key: str
    runs: list[UiRun] = field(default_factory=list)
    selected_run_id: str | None = None
    last_run_id: str | None = None

    def remember_run(self, run: UiRun) -> None:
        if run.run_id is None:
            return
        self.selected_run_id = run.run_id
        self.last_run_id = run.run_id

    def find_run(self, run_id: str) -> UiRun | None:
        for run in self.runs:
            if run.run_id == run_id:
                return run
        return None

    def ensure_run(self, run_id: str, *, raw_args: str = "<external>") -> UiRun:
        existing = self.find_run(run_id)
        if existing is not None:
            return existing

        run = UiRun(raw_args=raw_args, run_id=run_id, status="UNKNOWN")
        self.runs.append(run)
        return run


def build_session(session_key: str | None = None) -> UiSession:
    return UiSession(session_key=session_key or build_session_key())
