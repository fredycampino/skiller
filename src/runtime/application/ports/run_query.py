from typing import Any, Protocol


class RunQueryPort(Protocol):
    def get_status(self, run_id: str) -> dict[str, Any] | None:
        ...

    def get_logs(self, run_id: str) -> list[dict[str, Any]]:
        ...
