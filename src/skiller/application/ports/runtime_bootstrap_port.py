from typing import Protocol


class RuntimeBootstrapPort(Protocol):
    def init_db(self) -> None: ...
