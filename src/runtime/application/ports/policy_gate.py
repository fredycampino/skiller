from typing import Any, Protocol


class PolicyGatePort(Protocol):
    def authorize(self, skill_name: str, step: dict[str, Any]) -> bool:
        ...
