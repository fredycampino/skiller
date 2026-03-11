from __future__ import annotations

import json
import os
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any

from mcp import types


def _allowed_roots() -> list[Path]:
    raw = (os.getenv("FILES_ALLOWED_ROOTS") or "").strip()
    if not raw:
        return []
    return [Path(item).resolve() for item in raw.split(os.pathsep) if item.strip()]


def _is_allowed(path: Path) -> bool:
    resolved = path.resolve()
    for root in _allowed_roots():
        if resolved.is_relative_to(root):
            return True
    return False


def _build_initialize_result() -> dict[str, Any]:
    result = types.InitializeResult(
        protocolVersion=types.LATEST_PROTOCOL_VERSION,
        capabilities=types.ServerCapabilities(
            experimental={},
            tools=types.ToolsCapability(listChanged=True),
        ),
        serverInfo=types.Implementation(
            name="test-file-mcp",
            version=version("mcp"),
        ),
    )
    return result.model_dump(mode="json", by_alias=True, exclude_none=True)


def _build_tools_result() -> dict[str, Any]:
    result = types.ListToolsResult(
        tools=[
            types.Tool(
                name="files_action",
                description="Create a file inside configured allowed roots.",
                inputSchema={
                    "type": "object",
                    "required": ["action", "path"],
                    "properties": {
                        "action": {"type": "string"},
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                },
            )
        ]
    )
    return result.model_dump(mode="json", by_alias=True, exclude_none=True)


def _build_call_result(payload: dict[str, Any], *, is_error: bool) -> dict[str, Any]:
    result = types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=json.dumps(payload, ensure_ascii=True),
            )
        ],
        structuredContent=payload,
        isError=is_error,
    )
    return result.model_dump(mode="json", by_alias=True, exclude_none=True)


def _create_file(path: str, content: str) -> dict[str, Any]:
    target = Path(path)

    if not _is_allowed(target):
        return {
            "status": "error",
            "action": "create",
            "data": {},
            "message": "Access denied",
        }

    resolved = target.resolve()
    if resolved.exists():
        return {
            "status": "error",
            "action": "create",
            "data": {},
            "message": "File already exists",
        }

    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return {
        "status": "success",
        "action": "create",
        "data": {"path": str(resolved)},
        "message": "File created successfully",
    }


def _build_tool_call_result(params: dict[str, Any]) -> dict[str, Any]:
    tool_name = str(params.get("name", "")).strip()
    arguments = params.get("arguments", {})
    if tool_name != "files_action" or not isinstance(arguments, dict):
        payload = {
            "status": "error",
            "action": "unknown",
            "data": {},
            "message": "Unsupported tool",
        }
        return _build_call_result(payload, is_error=True)

    action = str(arguments.get("action", "")).strip()
    path = str(arguments.get("path", "")).strip()
    content = str(arguments.get("content", ""))

    if action != "create":
        payload = {
            "status": "error",
            "action": action or "unknown",
            "data": {},
            "message": "Unsupported action",
        }
        return _build_call_result(payload, is_error=True)

    payload = _create_file(path, content)
    return _build_call_result(payload, is_error=payload["status"] == "error")


def _write_payload(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def _write_response(request_id: int | str, result: dict[str, Any]) -> None:
    response = types.JSONRPCResponse(jsonrpc="2.0", id=request_id, result=result)
    _write_payload(response.model_dump(mode="json", by_alias=True, exclude_none=True))


def _write_error(request_id: int | str, *, code: int, message: str) -> None:
    response = types.JSONRPCError(
        jsonrpc="2.0",
        id=request_id,
        error=types.ErrorData(code=code, message=message),
    )
    _write_payload(response.model_dump(mode="json", by_alias=True, exclude_none=True))


def main() -> int:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = str(message.get("method", "")).strip()
        request_id = message.get("id")

        if method == "initialize" and request_id is not None:
            _write_response(request_id, _build_initialize_result())
            continue

        if method == "notifications/initialized":
            continue

        if method == "ping" and request_id is not None:
            _write_response(request_id, {})
            continue

        if method == "tools/list" and request_id is not None:
            _write_response(request_id, _build_tools_result())
            continue

        if method == "tools/call" and request_id is not None:
            params = message.get("params", {})
            if not isinstance(params, dict):
                _write_error(request_id, code=-32602, message="Invalid params")
                continue
            _write_response(request_id, _build_tool_call_result(params))
            continue

        if request_id is not None:
            _write_error(request_id, code=-32601, message=f"Method not found: {method}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
