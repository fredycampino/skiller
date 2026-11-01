from __future__ import annotations

import asyncio

import pytest

from skiller.domain.mcp.mcp_config_model import RenderedMcpConfig
from skiller.infrastructure.tools.mcp.client import MCPClientTool, MCPResolvedTarget

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def stub_mcp_calls() -> None:
    """Override packages/skiller/tests/conftest.py autouse fixture for this module."""
    return None


def test_resolve_target_builds_stdio_transport_from_config() -> None:
    client = MCPClientTool()
    target = client._resolve_server_target(
        "local-mcp",
        config=RenderedMcpConfig(
            name="local-mcp",
            transport="stdio",
            command="/usr/bin/python3",
            args=["/tmp/local_mcp.py"],
            cwd="/tmp",
            env={"FILES_ALLOWED_ROOTS": "/tmp/work"},
        ),
    )

    config = target.transport["mcpServers"]["local-mcp"]
    assert target.endpoint == "stdio:///usr/bin/python3"
    assert config["transport"] == "stdio"
    assert config["command"] == "/usr/bin/python3"
    assert config["args"] == ["/tmp/local_mcp.py"]
    assert config["cwd"] == "/tmp"
    assert config["keep_alive"] is False
    assert config["env"]["MCP_TRANSPORT"] == "stdio"
    assert config["env"]["FILES_ALLOWED_ROOTS"] == "/tmp/work"


def test_resolve_target_builds_http_transport_from_config() -> None:
    client = MCPClientTool()
    target = client._resolve_server_target(
        "chrome-mcp",
        config=RenderedMcpConfig(
            name="chrome-mcp",
            transport="streamable-http",
            url="http://127.0.0.1:7821/mcp",
        ),
    )

    assert target.endpoint == "http://127.0.0.1:7821/mcp"
    assert target.transport == "http://127.0.0.1:7821/mcp"


def test_resolve_target_builds_http_transport_with_headers_from_config() -> None:
    client = MCPClientTool()
    target = client._resolve_server_target(
        "github",
        config=RenderedMcpConfig(
            name="github",
            transport="streamable-http",
            url="https://api.github.example/mcp",
            headers={"Authorization": "Bearer secret-token"},
        ),
    )

    assert target.endpoint == "https://api.github.example/mcp"
    assert target.transport.url == "https://api.github.example/mcp"
    assert target.transport.headers == {"Authorization": "Bearer secret-token"}


def test_resolve_target_requires_config() -> None:
    client = MCPClientTool()

    with pytest.raises(ValueError, match="Missing MCP config"):
        client._resolve_server_target("local-mcp")


def test_call_inside_running_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call_tool(  # noqa: ANN202
        self,
        transport: object,
        tool_name: str,
        args: dict[str, object],
    ) -> dict[str, str]:
        _ = (self, transport, tool_name, args)
        return {"status": "success"}

    monkeypatch.setattr(MCPClientTool, "_call_tool", fake_call_tool)

    async def run_call() -> dict[str, object]:
        return MCPClientTool().call(
            "mcp.local-mcp.files_action",
            {"action": "list"},
            config=RenderedMcpConfig(
                name="local-mcp",
                transport="stdio",
                command="/usr/bin/python3",
            ),
        )

    result = asyncio.run(run_call())
    assert result["ok"] is True
    assert result["result"] == {"status": "success"}


def test_probe_server_reports_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_list_tools(self, transport: object) -> list[str]:  # noqa: ANN202
        _ = (self, transport)
        return ["files_action", "get_url"]

    monkeypatch.setattr(
        MCPClientTool,
        "_resolve_server_target",
        lambda self, server_name, config=None: MCPResolvedTarget(
            transport="http://127.0.0.1:7821/mcp",
            endpoint="http://127.0.0.1:7821/mcp",
        ),
    )
    monkeypatch.setattr(MCPClientTool, "_list_tools", fake_list_tools)

    result = MCPClientTool().probe_server(
        "local-mcp",
        config=RenderedMcpConfig(
            name="local-mcp",
            transport="streamable-http",
            url="http://127.0.0.1:7821/mcp",
        ),
    )

    assert result["ok"] is True
    assert result["server"] == "local-mcp"
    assert result["endpoint"] == "http://127.0.0.1:7821/mcp"
    assert result["tools_count"] == 2
    assert result["tools"] == ["files_action", "get_url"]
