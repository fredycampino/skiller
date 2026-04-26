from typing import Any

from skiller.application.ports.mcp_port import MCPPort
from skiller.domain.mcp.mcp_config_model import RenderedMcpConfig
from skiller.infrastructure.tools.mcp.client import MCPClientTool


class DefaultMCP(MCPPort):
    def __init__(self, mcp_client: MCPClientTool | None = None) -> None:
        self.mcp_client = mcp_client or MCPClientTool()

    def connect(self, server_name: str, config: RenderedMcpConfig | None = None) -> dict[str, Any]:
        return self._probe_server(server_name, config=config)

    def probe(self, server_name: str, config: RenderedMcpConfig | None = None) -> dict[str, Any]:
        return self._probe_server(server_name, config=config)

    def list_tools(self, server_name: str, config: RenderedMcpConfig | None = None) -> list[str]:
        result = self._probe_server(server_name, config=config)
        if not bool(result.get("ok")):
            raise RuntimeError(str(result.get("error", "Unknown MCP connection error")))
        tools = result.get("tools", [])
        return [str(item) for item in tools] if isinstance(tools, list) else []

    def call_tool(
        self,
        server_name: str,
        tool_name: str,
        args: dict[str, Any],
        config: RenderedMcpConfig | None = None,
    ) -> dict[str, Any]:
        if config is None:
            return self.mcp_client.call(f"mcp.{server_name}.{tool_name}", args)
        return self.mcp_client.call(f"mcp.{server_name}.{tool_name}", args, config=config)

    def read_resource(
        self,
        server_name: str,
        uri: str,
        config: RenderedMcpConfig | None = None,
    ) -> dict[str, Any]:
        if config is None:
            return self.mcp_client.read_resource(server_name, uri)
        return self.mcp_client.read_resource(server_name, uri, config=config)

    def _probe_server(
        self,
        server_name: str,
        config: RenderedMcpConfig | None = None,
    ) -> dict[str, Any]:
        if config is None:
            return self.mcp_client.probe_server(server_name)
        return self.mcp_client.probe_server(server_name, config=config)
