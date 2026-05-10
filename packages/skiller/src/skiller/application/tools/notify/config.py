from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from skiller.domain.tool.tool_contract import ToolConfig


def _notify_parameters_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "message": {"type": "string"},
        },
        "required": ["message"],
        "additionalProperties": False,
    }


@dataclass(frozen=True)
class NotifyToolConfig(ToolConfig):
    name: str = "notify"
    description: str = "Send a notification message to the active channel"
    parameters_schema: Mapping[str, object] = field(
        default_factory=_notify_parameters_schema
    )
