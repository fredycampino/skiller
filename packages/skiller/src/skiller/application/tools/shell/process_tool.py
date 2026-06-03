import os
from dataclasses import replace
from pathlib import Path
from typing import ClassVar, Mapping

from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.application.tools.shell.models import ShellToolRequest
from skiller.application.tools.shell.policy import ShellCommandPolicy
from skiller.application.tools.shell.runtime_config_mapper import (
    ShellToolRuntimeConfigMapper,
)
from skiller.domain.tool.tool_contract import (
    ConfiguredTool,
    ProcessTool,
    ToolDefinition,
    ToolInput,
    ToolPolicy,
    ToolPolicyResult,
    ToolRequestResult,
    ToolResult,
    ToolResultStatus,
    ToolRuntimeConfig,
    ToolSchema,
)
from skiller.domain.tool.tool_process_model import ToolProcessOutput, ToolProcessRequest


class ShellProcessTool(
    ToolDefinition[ShellToolRequest],
    ProcessTool[ShellToolRequest],
    ToolPolicy[ShellToolRequest],
    ConfiguredTool[ShellToolRuntimeConfig],
):
    name: ClassVar[str] = "shell"
    description: ClassVar[str] = "Execute a shell command in allowed paths"

    def __init__(
        self,
        *,
        shell: str | None = None,
    ) -> None:
        self.shell = shell

    def schema(self) -> ToolSchema:
        return ToolSchema(
            value={
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "cwd": {"type": "string"},
                    "env": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                    "timeout": {"type": "integer"},
                },
                "required": ["command"],
                "additionalProperties": False,
            }
        )

    def to_runtime_config(
        self,
        raw: Mapping[str, object],
    ) -> ShellToolRuntimeConfig:
        mapper = ShellToolRuntimeConfigMapper()
        return mapper.from_mapping(
            raw=raw,
            definition=type(self),
        )

    def request(self, input: ToolInput) -> ToolRequestResult[ShellToolRequest]:
        try:
            return ToolRequestResult.valid(
                ShellToolRequest(
                    command=input.require_string("command"),
                    cwd=input.optional_string("cwd"),
                    env=input.optional_string_map("env"),
                    timeout=input.optional_number("timeout"),
                )
            )
        except ValueError as exc:
            return ToolRequestResult.invalid(str(exc))

    def policy(
        self,
        *,
        config: ToolRuntimeConfig | None,
        request: ShellToolRequest,
    ) -> ToolPolicyResult[ShellToolRequest]:
        if not isinstance(config, ShellToolRuntimeConfig):
            return ToolPolicyResult.blocked("Tool 'shell' requires shell runtime config")
        command_policy = ShellCommandPolicy(config=config)
        effective_cwd = command_policy.resolve_cwd(request.cwd)
        try:
            command_policy.validate_command(
                command=request.command,
                effective_cwd=effective_cwd,
            )
        except ValueError as exc:
            return ToolPolicyResult.blocked(str(exc))
        return ToolPolicyResult.allowed(replace(request, effective_cwd=effective_cwd))

    def call(
        self,
        *,
        config: ToolRuntimeConfig | None,
        request: ShellToolRequest,
    ) -> ToolProcessRequest:
        if not isinstance(config, ShellToolRuntimeConfig):
            raise ValueError("Tool 'shell' requires shell runtime config")
        command_policy = ShellCommandPolicy(config=config)
        return ToolProcessRequest(
            command=[self._resolve_shell(), "-lc", request.command],
            cwd=request.effective_cwd or command_policy.resolve_cwd(request.cwd),
            env=dict(request.env or {}),
            timeout=request.timeout,
        )

    def result(self, output: ToolProcessOutput) -> ToolResult:
        data = {
            "ok": output.exit_code == 0,
            "exit_code": output.exit_code,
            "stdout": output.stdout,
            "stderr": output.stderr,
        }
        return ToolResult(
            name=self.name,
            status=ToolResultStatus.COMPLETED,
            data=data,
            text=self._build_summary_text(data),
            error=None,
        )

    def _resolve_shell(self) -> str:
        if self.shell is not None:
            return self.shell

        env_shell = os.getenv("SHELL", "").strip()
        if env_shell and Path(env_shell).is_file() and os.access(env_shell, os.X_OK):
            return env_shell

        for candidate in ("/bin/bash", "/bin/sh"):
            path = Path(candidate)
            if path.is_file() and os.access(path, os.X_OK):
                return candidate

        raise RuntimeError("No executable shell found. Tried $SHELL, /bin/bash and /bin/sh")

    def _build_summary_text(self, data: dict[str, object]) -> str:
        ok = bool(data.get("ok"))
        exit_code = int(data.get("exit_code", 0))
        stdout = str(data.get("stdout", "")).strip()
        stderr = str(data.get("stderr", "")).strip()

        if stdout:
            return stdout

        if ok:
            return "Command completed successfully."

        if stderr:
            return stderr

        return f"Command failed with exit code {exit_code}."
