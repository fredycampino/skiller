from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, TypeVar


@dataclass(frozen=True)
class ToolRequest:
    pass


class ToolResultStatus(str, Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ToolResult:
    name: str
    status: ToolResultStatus
    data: dict[str, Any]
    text: str | None = None
    error: str | None = None


RequestT = TypeVar("RequestT", bound=ToolRequest)
ResultT = TypeVar("ResultT", bound=ToolResult)


class Tool(ABC, Generic[RequestT, ResultT]):
    name: str

    @abstractmethod
    def execute(self, request: RequestT) -> ResultT:
        raise NotImplementedError
