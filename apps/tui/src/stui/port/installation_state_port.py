from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class InstallationState:
    runtime_db_exists: bool
    agent_config_exists: bool


class InstallationStatePort(Protocol):
    def read(self) -> InstallationState: ...
