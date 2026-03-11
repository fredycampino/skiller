from __future__ import annotations

import pytest

from skiller.infrastructure.tools.mcp.client import MCPClientTool


@pytest.fixture(autouse=True)
def stub_mcp_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid external MCP dependencies in unit tests."""

    def fake_call(self, tool_name, args):  # noqa: ANN001
        return {
            "ok": True,
            "tool": tool_name,
            "args": args,
            "stub": True,
        }

    def fake_probe_server(self, server_name):  # noqa: ANN001
        return {
            "ok": True,
            "server": server_name,
            "endpoint": "stub://mcp",
            "tools_count": 1,
            "tools": ["stub_tool"],
        }

    monkeypatch.setattr(MCPClientTool, "call", fake_call)
    monkeypatch.setattr(MCPClientTool, "probe_server", fake_probe_server)
