from typing import Any


class MCPClientTool:
    def call(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        # Paso 0: stub. En pasos siguientes se conecta a un cliente MCP real.
        return {"ok": True, "tool": tool_name, "args": args, "stub": True}
