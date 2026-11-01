from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from skiller.domain.mcp.mcp_config_model import RenderedMcpConfig
from skiller.infrastructure.tools.mcp.client import MCPClientTool
from skiller.infrastructure.tools.mcp.default_mcp import DefaultMCP

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def stub_mcp_calls() -> None:
    """Override packages/skiller/tests/conftest.py autouse fixture for this module."""
    return None


def _pick_free_port() -> int:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])
    except PermissionError:
        pytest.skip("Local TCP sockets are not available in this environment")


@pytest.fixture
def http_mcp_config() -> Iterator[RenderedMcpConfig]:
    port = _pick_free_port()
    server_script = (
        Path(__file__).parents[1] / "runtime" / "fixtures" / "mcp" / "test_mcp_server.py"
    )
    config = RenderedMcpConfig(
        name="test-mcp-int",
        transport="streamable-http",
        url=f"http://127.0.0.1:{port}/mcp",
    )
    process = subprocess.Popen(  # noqa: S603
        [sys.executable, str(server_script)],
        env={
            **os.environ,
            "MCP_TRANSPORT": "streamable-http",
            "MCP_HOST": "127.0.0.1",
            "MCP_PORT": str(port),
            "MCP_PATH": "/mcp",
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        client = MCPClientTool()
        deadline = time.monotonic() + 8.0
        while not client.probe_server(config.name, config=config)["ok"]:
            if process.poll() is not None:
                pytest.fail(f"MCP fixture exited with code {process.returncode}")
            if time.monotonic() >= deadline:
                pytest.fail("MCP fixture did not become ready")
            time.sleep(0.1)
        yield config
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_mcp_probe_and_operations_integration(http_mcp_config: RenderedMcpConfig) -> None:
    config = http_mcp_config
    server_name = config.name

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
