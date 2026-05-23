from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Generic, Mapping, Protocol, TypeVar, runtime_checkable

from skiller.domain.tool.tool_process_model import ToolProcessOutput, ToolProcessRequest


@dataclass(frozen=True)
class ToolSchema:
    value: Mapping[str, object]


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


RequestT = TypeVar("RequestT", bound=ToolRequest)


class ToolDefinition(ABC, Generic[RequestT]):
    name: ClassVar[str]
    description: ClassVar[str]

    @abstractmethod
    def schema(self) -> ToolSchema: ...

    @abstractmethod
    def request(self, input: ToolInput) -> "ToolRequestResult[RequestT]": ...


@dataclass(frozen=True)
class ToolRuntimeConfig:
    definition: type[ToolDefinition]


@dataclass(frozen=True)
class ToolRuntimeConfigs:
    items: tuple[ToolRuntimeConfig, ...] = ()

    def __post_init__(self) -> None:
        names: set[str] = set()
        for item in self.items:
            name = item.definition.name
            if name in names:
                raise RuntimeError(f"Duplicated runtime config for tool '{name}'")
            names.add(name)

    def get(self, name: str) -> ToolRuntimeConfig | None:
        for item in self.items:
            if item.definition.name == name:
                return item
        return None


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


ConfigT = TypeVar("ConfigT", bound=ToolRuntimeConfig)


@runtime_checkable
class ConfiguredTool(Protocol[ConfigT]):
    def to_runtime_config(
        self,
        raw: Mapping[str, object],
    ) -> ConfigT: ...


@runtime_checkable
class Tool(Protocol[RequestT]):
    def run(
        self,
        *,
        config: ToolRuntimeConfig | None,
        request: RequestT,
    ) -> ToolResult: ...


@runtime_checkable
class ProcessTool(Protocol[RequestT]):
    def call(
        self,
        *,
        config: ToolRuntimeConfig | None,
        request: RequestT,
    ) -> ToolProcessRequest: ...

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
    def policy(
        self,
        *,
        config: ToolRuntimeConfig | None,
        request: RequestT,
    ) -> ToolPolicyResult[RequestT]: ...
