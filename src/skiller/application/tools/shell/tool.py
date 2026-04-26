from dataclasses import dataclass

from skiller.application.ports.shell_port import ShellPort
from skiller.domain.tool.tool_contract import Tool, ToolRequest, ToolResult, ToolResultStatus


@dataclass(frozen=True)
class ShellToolRequest(ToolRequest):
    command: str
    cwd: str | None = None
    env: dict[str, str] | None = None
    timeout: int | None = None


class ShellTool(Tool[ShellToolRequest, ToolResult]):
    name = "shell"

    def __init__(self, shell: ShellPort) -> None:
        self.shell = shell

    def execute(self, request: ShellToolRequest) -> ToolResult:
        result = self.shell.run(
            command=request.command,
            cwd=request.cwd,
            env=request.env,
            timeout=request.timeout,
        )
        data = {
            "ok": bool(result.get("ok")),
            "exit_code": int(result.get("exit_code", 0)),
            "stdout": str(result.get("stdout", "")),
            "stderr": str(result.get("stderr", "")),
        }
        return ToolResult(
            name=self.name,
            status=ToolResultStatus.COMPLETED,
            data=data,
            text=self._build_summary_text(data),
            error=None,
        )

    def _build_summary_text(self, data: dict[str, object]) -> str:
        ok = bool(data.get("ok"))
        exit_code = int(data.get("exit_code", 0))
        stdout = str(data.get("stdout", "")).strip()
        stderr = str(data.get("stderr", "")).strip()

        if stdout:
            first_line = stdout.splitlines()[0].strip()
            if first_line:
                return first_line

        if ok:
            return "Command completed successfully."

        if stderr:
            first_line = stderr.splitlines()[0].strip()
            if first_line:
                return first_line

        return f"Command failed with exit code {exit_code}."
