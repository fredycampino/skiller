from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ScreenStatus(StrEnum):
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    ERROR = "error"


@dataclass(frozen=True)
class TranscriptItem:
    pass


@dataclass(frozen=True)
class UserInputItem(TranscriptItem):
    text: str


@dataclass(frozen=True)
class InfoItem(TranscriptItem):
    text: str


@dataclass(frozen=True)
class DispatchErrorItem(TranscriptItem):
    message: str


@dataclass(frozen=True)
class RunAckItem(TranscriptItem):
    skill: str
    run_id: str


@dataclass(frozen=True)
class RunStepItem(TranscriptItem):
    run_id: str
    step_type: str
    step_id: str


@dataclass(frozen=True)
class RunOutputItem(TranscriptItem):
    run_id: str
    step_type: str
    output: str


@dataclass(frozen=True)
class RunStatusItem(TranscriptItem):
    run_id: str
    status: str
    message: str = ""


@dataclass
class ConsoleScreenState:
    session_key: str = "main"
    screen_status: ScreenStatus = ScreenStatus.READY
    transcript_items: list[TranscriptItem] = field(default_factory=list)
