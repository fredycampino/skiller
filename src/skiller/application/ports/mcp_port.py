from typing import Any, Protocol

from skiller.domain.mcp_config_model import RenderedMcpConfig


class MCPPort(Protocol):
    def connect(self, server_name: str, config: RenderedMcpConfig | None = None) -> dict[str, Any]:
        ...

    def probe(self, server_name: str, config: RenderedMcpConfig | None = None) -> dict[str, Any]:
        ...

    def list_tools(self, server_name: str, config: RenderedMcpConfig | None = None) -> list[str]:
        ...

    def call_tool(
        self,
        server_name: str,
        tool_name: str,
        args: dict[str, Any],
        config: RenderedMcpConfig | None = None,
    ) -> dict[str, Any]:
        ...

    def read_resource(
        self,
        server_name: str,
        uri: str,
        config: RenderedMcpConfig | None = None,
    ) -> dict[str, Any]:
        ...
