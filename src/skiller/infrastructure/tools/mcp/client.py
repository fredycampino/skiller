from __future__ import annotations

import asyncio
import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

from skiller.domain.mcp_config_model import RenderedMcpConfig


@dataclass(frozen=True)
class MCPResolvedTarget:
    transport: Any
    endpoint: str


class MCPClientTool:
    _managed_processes: dict[str, subprocess.Popen[Any]] = {}

    def call(
        self, tool_name: str, args: dict[str, Any], config: RenderedMcpConfig | None = None
    ) -> dict[str, Any]:
        server_name, remote_tool_name = self._parse_tool_name(tool_name)
        target = self._resolve_server_target(server_name, config=config)
        self._maybe_start_http_server(server_name, target.endpoint)

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
            self._maybe_start_http_server(server_name, target.endpoint)
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
            self._maybe_start_http_server(server_name, target.endpoint)
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

    def _maybe_start_http_server(self, server_name: str, endpoint: str) -> None:
        if not endpoint.startswith("http"):
            return

        config = self._read_autostart_config(server_name)
        if config is None:
            return

        if self._is_endpoint_ready(endpoint):
            return

        process = self._managed_processes.get(server_name)
        if process is not None and process.poll() is None:
            self._wait_until_endpoint_ready(
                endpoint, process, timeout_seconds=config["timeout_seconds"]
            )
            return

        env = os.environ.copy()
        env.update(config["env"])
        self._inject_http_server_env_defaults(env, endpoint)

        process = subprocess.Popen(  # noqa: S603
            [config["command"], *config["args"]],
            cwd=config["cwd"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._managed_processes[server_name] = process
        self._wait_until_endpoint_ready(
            endpoint, process, timeout_seconds=config["timeout_seconds"]
        )

    def _read_autostart_config(self, server_name: str) -> dict[str, Any] | None:
        env_prefix = f"AGENT_MCP_{server_name.upper().replace('-', '_')}"
        command = (os.getenv(f"{env_prefix}_AUTOSTART_COMMAND") or "").strip()
        if not command:
            return None

        return {
            "command": command,
            "args": self._parse_json_list_env(f"{env_prefix}_AUTOSTART_ARGS"),
            "env": {
                str(k): str(v)
                for k, v in self._parse_json_object_env(f"{env_prefix}_AUTOSTART_ENV").items()
            },
            "cwd": (os.getenv(f"{env_prefix}_AUTOSTART_CWD") or "").strip() or None,
            "timeout_seconds": self._parse_timeout_seconds(
                f"{env_prefix}_AUTOSTART_TIMEOUT", default=10.0
            ),
        }

    def _wait_until_endpoint_ready(
        self,
        endpoint: str,
        process: subprocess.Popen[Any],
        *,
        timeout_seconds: float,
    ) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(
                    "MCP autostart process exited with code "
                    f"{process.returncode} before endpoint became ready: {endpoint}"
                )
            if self._is_endpoint_ready(endpoint):
                return
            time.sleep(0.2)

        raise RuntimeError(f"MCP endpoint did not become ready before timeout: {endpoint}")

    def _is_endpoint_ready(self, endpoint: str) -> bool:
        try:
            ready = self._run_async(lambda: self._probe_endpoint(endpoint))
            return bool(ready)
        except Exception:  # noqa: BLE001
            return False

    async def _probe_endpoint(self, endpoint: str) -> bool:
        from fastmcp import Client

        try:
            async with Client(endpoint, init_timeout=1.5, timeout=1.5) as client:
                await client.list_tools()
            return True
        except Exception:  # noqa: BLE001
            return False

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
    def _inject_http_server_env_defaults(env: dict[str, str], endpoint: str) -> None:
        parsed = urlparse(endpoint)
        env.setdefault("MCP_TRANSPORT", "streamable-http")
        if parsed.hostname:
            env.setdefault("MCP_HOST", parsed.hostname)
        if parsed.port:
            env.setdefault("MCP_PORT", str(parsed.port))
        if parsed.path:
            env.setdefault("MCP_PATH", parsed.path)

    @staticmethod
    def _parse_timeout_seconds(env_name: str, *, default: float) -> float:
        raw = (os.getenv(env_name) or "").strip()
        if not raw:
            return default
        try:
            timeout = float(raw)
        except ValueError as exc:
            raise ValueError(f"Invalid {env_name}. Expected a numeric value in seconds.") from exc
        if timeout <= 0:
            raise ValueError(f"Invalid {env_name}. Timeout must be > 0.")
        return timeout

    @staticmethod
    def _parse_json_list_env(env_name: str) -> list[str]:
        raw = (os.getenv(env_name) or "").strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {env_name}. Expected a JSON array.") from exc

        if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
            raise ValueError(f"Invalid {env_name}. Expected a JSON array of strings.")
        return data

    @staticmethod
    def _parse_json_object_env(env_name: str) -> dict[str, Any]:
        raw = (os.getenv(env_name) or "").strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {env_name}. Expected a JSON object.") from exc

        if not isinstance(data, dict):
            raise ValueError(f"Invalid {env_name}. Expected a JSON object.")
        return data

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
