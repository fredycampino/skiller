from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

import pytest

from skiller.domain.mcp_config_model import RenderedMcpConfig
from skiller.infrastructure.tools.mcp.client import MCPClientTool
from skiller.infrastructure.tools.mcp.default_mcp import DefaultMCP

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def stub_mcp_calls() -> None:
    """Override tests/conftest.py autouse fixture for this module."""
    return None


def _pick_free_port() -> int:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])
    except PermissionError:
        pytest.skip("Local TCP sockets are not available in this environment")


def _configure_test_mcp_autostart(
    monkeypatch: pytest.MonkeyPatch, *, server_name: str, port: int
) -> RenderedMcpConfig:
    server_script = (
        Path(__file__).parents[1] / "runtime" / "fixtures" / "mcp" / "test_mcp_server.py"
    )
    assert server_script.exists(), f"MCP fixture server script not found: {server_script}"

    prefix = f"AGENT_MCP_{server_name.upper().replace('-', '_')}"
    endpoint = f"http://127.0.0.1:{port}/mcp"

    monkeypatch.setenv(f"{prefix}_AUTOSTART_COMMAND", sys.executable)
    monkeypatch.setenv(f"{prefix}_AUTOSTART_ARGS", json.dumps([str(server_script)]))
    project_root = Path(__file__).parents[3]
    monkeypatch.setenv(f"{prefix}_AUTOSTART_CWD", str(project_root))
    monkeypatch.setenv(f"{prefix}_AUTOSTART_ENV", json.dumps({}))
    monkeypatch.setenv(f"{prefix}_AUTOSTART_TIMEOUT", "8")

    return RenderedMcpConfig(
        name=server_name,
        transport="streamable-http",
        url=endpoint,
    )


def test_mcp_probe_and_operations_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    server_name = "test-mcp-int"
    port = _pick_free_port()
    config = _configure_test_mcp_autostart(monkeypatch, server_name=server_name, port=port)

    client = MCPClientTool()
    probe_result = client.probe_server(server_name, config=config)

    assert probe_result["ok"] is True
    assert str(probe_result.get("endpoint", "")).startswith("http://127.0.0.1:")
    assert probe_result.get("tools_count", 0) > 0
    assert "ping" in probe_result.get("tools", [])

    mcp = DefaultMCP(mcp_client=client)

    tools = mcp.list_tools(server_name, config=config)
    assert "ping" in tools

    call_result = mcp.call_tool(server_name, "ping", {}, config=config)
    assert call_result["ok"] is True

    resource_result = mcp.read_resource(server_name, "docs://health", config=config)
    assert resource_result["ok"] is True
    assert resource_result["uri"] == "docs://health"
