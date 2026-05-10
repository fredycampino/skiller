import os
from dataclasses import replace
from pathlib import Path

from skiller.application.tools.shell.config import ShellToolConfig
from skiller.application.tools.shell.models import ShellToolRequest
from skiller.application.tools.shell.policy import ShellCommandPolicy
from skiller.domain.tool.tool_contract import (
    ProcessTool,
    ToolInput,
    ToolPolicy,
    ToolPolicyResult,
    ToolRequestResult,
    ToolResult,
    ToolResultStatus,
)
from skiller.domain.tool.tool_process_model import ToolProcessOutput, ToolProcessRequest


class ShellProcessTool(ProcessTool[ShellToolRequest], ToolPolicy[ShellToolRequest]):
    name = "shell"
    config = ShellToolConfig()

    def __init__(
        self,
        *,
        shell: str | None = None,
        workspace_root: str | None = None,
        allowlist_enabled: bool = False,
        allowed_commands: list[str] | None = None,
        allow_env_prefix: bool = True,
        sandbox_enabled: bool = False,
    ) -> None:
        self.shell = shell
        self.command_policy = ShellCommandPolicy(
            workspace_root=workspace_root,
            allowlist_enabled=allowlist_enabled,
            allowed_commands=allowed_commands,
            allow_env_prefix=allow_env_prefix,
            sandbox_enabled=sandbox_enabled,
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

    def policy(self, request: ShellToolRequest) -> ToolPolicyResult[ShellToolRequest]:
        effective_cwd = self.command_policy.resolve_cwd(request.cwd)
        try:
            self.command_policy.validate_command(
                command=request.command,
                effective_cwd=effective_cwd,
            )
        except ValueError as exc:
            return ToolPolicyResult.blocked(str(exc))
        return ToolPolicyResult.allowed(replace(request, effective_cwd=effective_cwd))

    def call(self, request: ShellToolRequest) -> ToolProcessRequest:
        return ToolProcessRequest(
            command=[self._resolve_shell(), "-lc", request.command],
            cwd=request.effective_cwd or self.command_policy.resolve_cwd(request.cwd),
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

    def format_timeout(self, timeout: int | float | None) -> str:
        if isinstance(timeout, int):
            return f"{timeout}s"
        if isinstance(timeout, float):
            return f"{timeout:g}s"
        return "unknown timeout"

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
