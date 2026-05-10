from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, Mapping, Protocol, TypeVar, runtime_checkable

from skiller.domain.tool.tool_process_model import ToolProcessOutput, ToolProcessRequest


@dataclass(frozen=True)
class ToolRequest:
    pass


@dataclass(frozen=True)
class ToolInput:
    run_id: str
    step_id: str
    tool_call_id: str
    args: Mapping[str, object]

    def require_string(self, name: str) -> str:
        value = self.args.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Tool call '{self.tool_call_id}' requires string {name}")
        return value

    def optional_string(self, name: str) -> str | None:
        value = self.args.get(name)
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"Tool call '{self.tool_call_id}' requires string {name}")
        value = value.strip()
        return value or None

    def optional_number(self, name: str) -> int | float | None:
        value = self.args.get(name)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Tool call '{self.tool_call_id}' requires number {name}")
        if value <= 0:
            raise ValueError(f"Tool call '{self.tool_call_id}' requires positive {name}")
        return value

    def optional_string_map(self, name: str) -> dict[str, str] | None:
        value = self.args.get(name)
        if value is None:
            return None
        if not isinstance(value, Mapping):
            raise ValueError(f"Tool call '{self.tool_call_id}' requires object {name}")

        result: dict[str, str] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(
                    f"Tool call '{self.tool_call_id}' requires non-empty string keys in {name}"
                )
            result[key] = str(item)
        return result


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


@dataclass(frozen=True)
class ToolRequestResult(Generic[RequestT]):
    ok: bool
    request: RequestT | None = None
    error: str | None = None

    @classmethod
    def valid(cls, request: RequestT) -> "ToolRequestResult[RequestT]":
        return cls(ok=True, request=request)

    @classmethod
    def invalid(cls, error: str) -> "ToolRequestResult[RequestT]":
        return cls(ok=False, error=error)


@runtime_checkable
class ToolSpec(Protocol):
    name: str
    config: ToolConfig

    def request(self, input: ToolInput) -> ToolRequestResult[ToolRequest]: ...


@runtime_checkable
class Tool(ToolSpec, Protocol[RequestT]):
    def run(self, request: RequestT) -> ToolResult: ...


@runtime_checkable
class ProcessTool(ToolSpec, Protocol[RequestT]):
    def call(self, request: RequestT) -> ToolProcessRequest: ...

    def result(self, output: ToolProcessOutput) -> ToolResult: ...


@dataclass(frozen=True)
class ToolPolicyResult(Generic[RequestT]):
    ok: bool
    request: RequestT | None = None
    error: str | None = None

    @classmethod
    def allowed(cls, request: RequestT) -> "ToolPolicyResult[RequestT]":
        return cls(ok=True, request=request)

    @classmethod
    def blocked(cls, error: str) -> "ToolPolicyResult[RequestT]":
        return cls(ok=False, error=error)


@runtime_checkable
class ToolPolicy(Protocol[RequestT]):
    def policy(self, request: RequestT) -> ToolPolicyResult[RequestT]: ...
