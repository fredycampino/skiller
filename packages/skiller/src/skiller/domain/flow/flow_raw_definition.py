from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FlowRawDefinition:
    name: str | None
    start: str | None
    steps: tuple["FlowRawStepDefinition", ...] | None
    on_success: "RawEndActionDefinition | None" = None
    on_error: "RawEndActionDefinition | None" = None
    raw: object | None = None


@dataclass(frozen=True)
class FlowRawStepDefinition:
    index: int | None
    step_id: str | None
    step_type: str | None
    body: dict[str, Any] | None
    raw: object | None = None


@dataclass(frozen=True)
class RawEndActionDefinition:
    trigger: str | None
    action: "RawAction | None"


@dataclass(frozen=True)
class RawAction:
    type: str | None
    label: str | None
    message: str | None = None
    url: str | None = None
    arg: str | None = None
    params: str | None = None
    auto: object | None = None
    raw: dict[str, Any] | None = None
