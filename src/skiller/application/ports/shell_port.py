from typing import Protocol


class ShellPort(Protocol):
    def run(
        self,
        *,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | float | None = None,
    ) -> dict[str, object]: ...
