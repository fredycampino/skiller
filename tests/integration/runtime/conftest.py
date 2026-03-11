from __future__ import annotations

import pytest

from skiller.infrastructure.tools.mcp.client import MCPClientTool


@pytest.fixture(autouse=True)
def stub_runtime_mcp_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub MCP for runtime integration tests that don't validate MCP transport."""

    def fake_call(self, tool_name, args, config=None):  # noqa: ANN001
        endpoint = None
        if config is not None:
            endpoint = config.url or (f"stdio://{config.command}" if config.command else None)
        return {
            "ok": True,
            "tool": tool_name,
            "args": args,
            "server": tool_name.split(".")[1] if tool_name.startswith("mcp.") else "",
            "endpoint": endpoint or "stub://mcp",
            "stub": True,
        }

    def fake_probe_server(self, server_name, config=None):  # noqa: ANN001
        endpoint = None
        if config is not None:
            endpoint = config.url or (f"stdio://{config.command}" if config.command else None)
        return {
            "ok": True,
            "server": server_name,
            "endpoint": endpoint or "stub://mcp",
            "tools_count": 1,
            "tools": ["stub_tool"],
        }

    monkeypatch.setattr(MCPClientTool, "call", fake_call)
    monkeypatch.setattr(MCPClientTool, "probe_server", fake_probe_server)
