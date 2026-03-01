from typing import Any, Protocol


class RuntimePort(Protocol):
    def start_run(self, skill_name: str, inputs: dict[str, Any]) -> str:
        ...

    def handle_webhook(self, wait_key: str, payload: dict[str, Any]) -> list[str]:
        ...
