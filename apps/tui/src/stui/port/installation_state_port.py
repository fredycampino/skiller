from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class InstallationErrorKind(StrEnum):
    COMMAND_FAILED = "command_failed"
    INVALID_RESPONSE = "invalid_response"


@dataclass(frozen=True)
class InstallationError:
    kind: InstallationErrorKind
    message: str


@dataclass(frozen=True)
class InstallationState:
    runtime_db_exists: bool
    error: InstallationError | None = None


class InstallationStatePort(Protocol):
    def read(self) -> InstallationState: ...
