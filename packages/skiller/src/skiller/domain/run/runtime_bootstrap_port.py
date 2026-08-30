from typing import Protocol


class RuntimeBootstrapError(RuntimeError):
    pass


class RuntimeBootstrapPort(Protocol):
    def init_db(self) -> None: ...
