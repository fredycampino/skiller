from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, Mapping, TypeVar


@dataclass(frozen=True)
class ToolRequest:
    pass


@dataclass(frozen=True)
class ToolConfig:
    name: str
    description: str
    parameters_schema: Mapping[str, object] = field(default_factory=dict)


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
