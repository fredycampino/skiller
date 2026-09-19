from typing import Protocol


class EnvironmentSecretPort(Protocol):
    def get_secret(self, name: str) -> str | None: ...
