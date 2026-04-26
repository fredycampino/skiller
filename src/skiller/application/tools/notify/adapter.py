from typing import Any

from skiller.application.tools.notify.tool import NotifyToolRequest
from skiller.application.tools.tool_adapter import ToolAdapter


class NotifyToolAdapter(ToolAdapter[NotifyToolRequest]):
    name = "notify"

    def build_request(self, *, step_id: str, value: dict[str, Any]) -> NotifyToolRequest:
        message = value.get("message")
        if not isinstance(message, str):
            raise ValueError(f"Notify tool in step '{step_id}' requires string message")
        return NotifyToolRequest(message=message)
