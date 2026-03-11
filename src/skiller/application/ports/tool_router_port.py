from typing import Any, Protocol


class ToolRouterPort(Protocol):
    def call(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        ...
