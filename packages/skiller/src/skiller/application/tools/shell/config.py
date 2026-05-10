from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from skiller.domain.tool.tool_contract import ToolConfig


def _shell_parameters_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "cwd": {"type": "string"},
            "env": {"type": "object"},
            "timeout": {"type": "integer"},
        },
        "required": ["command"],
        "additionalProperties": False,
    }


@dataclass(frozen=True)
class ShellToolConfig(ToolConfig):
    name: str = "shell"
    description: str = "Execute a shell command in the workspace"
    parameters_schema: Mapping[str, object] = field(
        default_factory=_shell_parameters_schema
    )
