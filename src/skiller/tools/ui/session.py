from __future__ import annotations

import uuid
from dataclasses import dataclass, field


def build_session_key() -> str:
    return uuid.uuid4().hex[:8]


def build_run_id() -> str:
    return str(uuid.uuid4())


@dataclass
class UiRun:
    run_id: str
    raw_args: str
    status: str = "CREATED"
    error: str | None = None


@dataclass
class UiSession:
    session_key: str
    runs: list[UiRun] = field(default_factory=list)


def build_session(session_key: str | None = None) -> UiSession:
    return UiSession(session_key=session_key or build_session_key())
