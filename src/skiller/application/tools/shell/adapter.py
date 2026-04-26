from typing import Any

from skiller.application.tools.shell.tool import ShellToolRequest
from skiller.application.tools.tool_adapter import ToolAdapter


class ShellToolAdapter(ToolAdapter[ShellToolRequest]):
    name = "shell"

    def build_request(self, *, step_id: str, value: dict[str, Any]) -> ShellToolRequest:
        return ShellToolRequest(
            command=self._parse_command(step_id=step_id, value=value.get("command")),
            cwd=self._parse_cwd(step_id=step_id, value=value.get("cwd")),
            env=self._parse_env(step_id=step_id, value=value.get("env")),
            timeout=self._parse_timeout(step_id=step_id, value=value.get("timeout")),
        )

    def format_timeout(self, timeout: int | None) -> str:
        if isinstance(timeout, int):
            return f"{timeout}s"
        return "unknown timeout"

    def _parse_command(self, *, step_id: str, value: object) -> str:
        command = value
        if not isinstance(command, str) or not command.strip():
            raise ValueError(f"Shell tool in step '{step_id}' requires command")
        return command

    def _parse_cwd(self, *, step_id: str, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"Shell tool in step '{step_id}' requires string cwd")
        cwd = value.strip()
        return cwd or None

    def _parse_env(self, *, step_id: str, value: object) -> dict[str, str] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError(f"Shell tool in step '{step_id}' env must be an object")

        env: dict[str, str] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(
                    f"Shell tool in step '{step_id}' env requires non-empty string keys"
                )
            env[key] = str(item)
        return env

    def _parse_timeout(self, *, step_id: str, value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"Shell tool in step '{step_id}' requires integer timeout")
        if value <= 0:
            raise ValueError(f"Shell tool in step '{step_id}' requires positive timeout")
        return value
