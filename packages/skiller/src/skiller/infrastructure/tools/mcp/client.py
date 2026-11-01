from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from skiller.domain.mcp.mcp_config_model import RenderedMcpConfig


@dataclass(frozen=True)
class MCPResolvedTarget:
    transport: Any
    endpoint: str


class MCPClientTool:
    def call(
        self, tool_name: str, args: dict[str, Any], config: RenderedMcpConfig | None = None
    ) -> dict[str, Any]:
        server_name, remote_tool_name = self._parse_tool_name(tool_name)
        target = self._resolve_server_target(server_name, config=config)

        try:
            payload = self._run_async(
                lambda: self._call_tool(target.transport, remote_tool_name, args)
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "tool": tool_name,
                "args": args,
                "server": server_name,
                "endpoint": target.endpoint,
                "error": str(exc),
            }

        ok = self._is_success_payload(payload)
        result: dict[str, Any] = {
            "ok": ok,
            "tool": tool_name,
            "args": args,
            "server": server_name,
            "endpoint": target.endpoint,
            "result": payload,
        }
        if not ok:
            result["error"] = self._extract_error_message(payload)

        return result

    def probe_server(
        self, server_name: str, config: RenderedMcpConfig | None = None
    ) -> dict[str, Any]:
        try:
            target = self._resolve_server_target(server_name, config=config)
            tools = self._run_async(lambda: self._list_tools(target.transport))
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "server": server_name,
                "error": str(exc),
            }
        return {
            "ok": True,
            "server": server_name,
            "endpoint": target.endpoint,
            "tools_count": len(tools),
            "tools": tools,
        }

    def read_resource(
        self,
        server_name: str,
        uri: str,
        config: RenderedMcpConfig | None = None,
    ) -> dict[str, Any]:
        try:
            target = self._resolve_server_target(server_name, config=config)
            payload = self._run_async(lambda: self._read_resource(target.transport, uri))
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "server": server_name,
                "endpoint": None,
                "uri": uri,
                "error": str(exc),
            }

        return {
            "ok": True,
            "server": server_name,
            "endpoint": target.endpoint,
            "uri": uri,
            "result": payload,
        }

    async def _call_tool(self, transport: Any, tool_name: str, args: dict[str, Any]) -> Any:
        try:
            from fastmcp import Client
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "fastmcp is required for MCP tool execution. "
                "Install project deps with 'pip install -e .'."
            ) from exc

        async with Client(transport, init_timeout=15.0, timeout=15.0) as client:
            response = await client.call_tool(tool_name, args)

        return self._extract_response_payload(response)

    async def _list_tools(self, transport: Any) -> list[str]:
        try:
            from fastmcp import Client
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "fastmcp is required for MCP connection checks. "
                "Install project deps with 'pip install -e .'."
            ) from exc

        async with Client(transport, init_timeout=15.0, timeout=15.0) as client:
            tools = await client.list_tools()

        names: list[str] = []
        for item in tools or []:
            name = getattr(item, "name", None)
            if isinstance(name, str) and name:
                names.append(name)
            else:
                names.append(str(item))
        return names

    async def _read_resource(self, transport: Any, uri: str) -> Any:
        try:
            from fastmcp import Client
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "fastmcp is required for MCP resource reads. "
                "Install project deps with 'pip install -e .'."
            ) from exc

        async with Client(transport, init_timeout=15.0, timeout=15.0) as client:
            response = await client.read_resource(uri)

        return self._extract_response_payload(response)

    @staticmethod
    def _parse_tool_name(tool_name: str) -> tuple[str, str]:
        parts = tool_name.split(".")
        if len(parts) < 3 or parts[0] != "mcp":
            raise ValueError(
                f"Invalid MCP tool name '{tool_name}'. Expected format: mcp.<server>.<tool>"
            )

        server = parts[1].strip()
        remote_tool = ".".join(parts[2:]).strip()
        if not server or not remote_tool:
            raise ValueError(f"Invalid MCP tool name '{tool_name}'. Missing server or tool segment")

        return server, remote_tool

    def _resolve_server_target(
        self,
        server_name: str,
        config: RenderedMcpConfig | None = None,
    ) -> MCPResolvedTarget:
        if config is None:
            raise ValueError(f"Missing MCP config for server '{server_name}'")

        return self._build_target_from_config(server_name, config)

    def _build_target_from_config(
        self, server_name: str, config: RenderedMcpConfig
    ) -> MCPResolvedTarget:
        if config.name != server_name:
            raise ValueError(
                f"MCP config name '{config.name}' does not match requested server '{server_name}'"
            )

        if config.transport in {"http", "streamable-http"}:
            if not config.url:
                raise ValueError(f"MCP server '{server_name}' requires url for http transport")
            transport = self._build_http_transport(config)
            return MCPResolvedTarget(transport=transport, endpoint=config.url)

        if config.transport == "stdio":
            if not config.command:
                raise ValueError(f"MCP server '{server_name}' requires command for stdio transport")

            stdio_env: dict[str, str] = {"MCP_TRANSPORT": "stdio"}
            stdio_env.update({str(k): str(v) for k, v in config.env.items()})

            server_config: dict[str, Any] = {
                "transport": "stdio",
                "command": config.command,
                "args": [str(item) for item in config.args],
                "env": stdio_env,
                "keep_alive": False,
            }
            if config.cwd:
                server_config["cwd"] = config.cwd

            transport = {"mcpServers": {server_name: server_config}}
            endpoint_label = f"stdio://{config.command}"
            return MCPResolvedTarget(transport=transport, endpoint=endpoint_label)

        raise ValueError(
            f"Unsupported MCP transport '{config.transport}' for server '{server_name}'"
        )

    def _build_http_transport(self, config: RenderedMcpConfig) -> Any:
        if not config.headers:
            return config.url

        try:
            from fastmcp.client.transports import StreamableHttpTransport
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "fastmcp is required for MCP HTTP headers support. "
                "Install project deps with 'pip install -e .'."
            ) from exc

        return StreamableHttpTransport(
            str(config.url),
            headers={str(key): str(value) for key, value in config.headers.items()},
        )

    @staticmethod
    def _run_async(awaitable_factory: Callable[[], Awaitable[Any]]) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(awaitable_factory())

        result: dict[str, Any] = {}
        error: dict[str, BaseException] = {}

        def runner() -> None:
            try:
                result["value"] = asyncio.run(awaitable_factory())
            except Exception as exc:  # noqa: BLE001
                error["error"] = exc

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join()

        if "error" in error:
            raise error["error"]
        return result.get("value")

    @staticmethod
    def _extract_response_payload(response: Any) -> Any:
        for attr in ("data", "structured_content"):
            value = getattr(response, attr, None)
            if value is not None:
                return value

        content = getattr(response, "content", None)
        if isinstance(content, list):
            texts: list[str] = []
            for item in content:
                text = getattr(item, "text", None)
                if isinstance(text, str) and text:
                    texts.append(text)

            if texts:
                first = texts[0].strip()
                if first:
                    try:
                        return json.loads(first)
                    except json.JSONDecodeError:
                        pass

                if len(texts) == 1:
                    return {"text": texts[0]}
                return {"texts": texts}

        return {"raw": str(response)}

    @staticmethod
    def _is_success_payload(payload: Any) -> bool:
        if isinstance(payload, dict):
            if isinstance(payload.get("ok"), bool):
                return bool(payload["ok"])

            status = payload.get("status")
            if isinstance(status, str):
                return status.lower() != "error"

        return True

    @staticmethod
    def _extract_error_message(payload: Any) -> str:
        if isinstance(payload, dict):
            for key in ("message", "error", "detail", "reason"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value

        return "MCP tool returned error status"
