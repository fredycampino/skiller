import pytest

from skiller.infrastructure.tools.mcp.default_mcp import DefaultMCP

pytestmark = pytest.mark.unit


class _FakeMCPClient:
    def probe_server(self, server_name: str):
        if server_name == "down":
            return {"ok": False, "error": "connection refused"}
        return {"ok": True, "server": server_name, "tools": ["a", "b"]}

    def call(self, tool_name: str, args: dict[str, object]):
        return {"ok": True, "tool": tool_name, "args": args}

    def read_resource(self, server_name: str, uri: str):
        return {"ok": True, "server": server_name, "uri": uri, "result": {"text": "hello"}}


def test_default_mcp_routes_calls() -> None:
    mcp = DefaultMCP(mcp_client=_FakeMCPClient())

    assert mcp.connect("local-mcp")["ok"] is True
    assert mcp.probe("local-mcp")["ok"] is True
    assert mcp.list_tools("local-mcp") == ["a", "b"]

    call_result = mcp.call_tool("local-mcp", "files_action", {"action": "list"})
    assert call_result["ok"] is True
    assert call_result["tool"] == "mcp.local-mcp.files_action"

    read_result = mcp.read_resource("local-mcp", "docs://files")
    assert read_result["ok"] is True
    assert read_result["uri"] == "docs://files"


def test_default_mcp_list_tools_raises_when_probe_fails() -> None:
    mcp = DefaultMCP(mcp_client=_FakeMCPClient())

    try:
        mcp.list_tools("down")
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert "connection refused" in str(exc)
