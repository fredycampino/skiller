from typing import Protocol


class ServerStatusPort(Protocol):
    def is_available(self) -> bool: ...
