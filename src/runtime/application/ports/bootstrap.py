from typing import Protocol


class RuntimeBootstrapPort(Protocol):
    def initialize(self) -> None:
        ...
