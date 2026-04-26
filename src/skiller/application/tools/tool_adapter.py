from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from skiller.domain.tool.tool_contract import ToolRequest

AdapterRequestT = TypeVar("AdapterRequestT", bound=ToolRequest)


class ToolAdapter(ABC, Generic[AdapterRequestT]):
    name: str

    @abstractmethod
    def build_request(self, *, step_id: str, value: dict[str, Any]) -> AdapterRequestT:
        raise NotImplementedError
