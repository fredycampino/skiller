from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class StoredSession:
    run_id: str
    run_name: str = ""


class SessionStorePort(Protocol):
    def read(self) -> StoredSession | None: ...

    def write(self, session: StoredSession) -> None: ...

    def clear(self) -> None: ...
