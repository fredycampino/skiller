from __future__ import annotations

import os

from fastmcp import FastMCP


mcp = FastMCP("test-mcp")


@mcp.tool()
async def ping() -> dict[str, bool]:
    return {"ok": True}


@mcp.resource("docs://health", mime_type="application/json")
def health() -> str:
    return '{"status":"ok"}'


if __name__ == "__main__":
    transport = (os.getenv("MCP_TRANSPORT") or "stdio").strip().lower()

    if transport == "stdio":
        mcp.run(transport="stdio", show_banner=False)
    elif transport in {"streamable-http", "streamable_http", "streamablehttp", "http"}:
        host = os.getenv("MCP_HOST", "127.0.0.1")
        port = int(os.getenv("MCP_PORT", "8765"))
        path = os.getenv("MCP_PATH", "/mcp")
        mcp.run(transport="http", host=host, port=port, path=path)
    else:
        raise SystemExit(f"Unsupported MCP_TRANSPORT={transport!r}")
