from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from skiller.domain.tool.tool_contract import ToolRuntimeConfig


@dataclass(frozen=True)
class ShellToolRuntimeConfig(ToolRuntimeConfig):
    allowed_paths: tuple[Path, ...] = ()
    allowlist_enabled: bool = False
    allow_env_prefix: bool = True
    allowed_commands: tuple[str, ...] = ()
