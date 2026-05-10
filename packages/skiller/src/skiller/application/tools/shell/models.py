from dataclasses import dataclass

from skiller.domain.tool.tool_contract import ToolRequest


@dataclass(frozen=True)
class ShellToolRequest(ToolRequest):
    command: str
    cwd: str | None = None
    effective_cwd: str | None = None
    env: dict[str, str] | None = None
    timeout: int | float | None = None
