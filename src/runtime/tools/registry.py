from typing import Any

from runtime.tools.internal.handlers import InternalTools
from runtime.tools.mcp.client import MCPClientTool


class ToolRouter:
    def __init__(self) -> None:
        self.internal = InternalTools()
        self.mcp = MCPClientTool()

    def call(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        if tool_name.startswith("mcp."):
            return self.mcp.call(tool_name, args)
        if tool_name.startswith("internal."):
            return self.internal.call(tool_name, args)
        raise ValueError(f"Unknown tool: {tool_name}")
