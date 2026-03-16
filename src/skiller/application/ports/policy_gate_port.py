from typing import Any, Protocol


class PolicyGatePort(Protocol):
    def authorize(self, skill_ref: str, step: dict[str, Any]) -> bool: ...
