from dataclasses import dataclass
from typing import Any

from skiller.domain.tool.tool_contract import ToolRuntimeConfig


@dataclass(frozen=True)
class AgentToolRequest:
    run_id: str
    step_id: str
    context_id: str
    turn_id: str
    tool_call_id: str
    tool: str
    args: dict[str, Any]
    allowed_tools: list[str]
    runtime_config: ToolRuntimeConfig | None
