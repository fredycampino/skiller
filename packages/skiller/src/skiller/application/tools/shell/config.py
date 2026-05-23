from __future__ import annotations

from dataclasses import dataclass

from skiller.domain.tool.tool_contract import ToolRuntimeConfig


@dataclass(frozen=True)
class ShellToolRuntimeConfig(ToolRuntimeConfig):
    workspace: str = ""
    allowlist_enabled: bool = False
    allow_env_prefix: bool = True
    allowed_commands: tuple[str, ...] = ()
