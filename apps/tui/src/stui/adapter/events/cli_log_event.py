from __future__ import annotations

from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from stui.port.event_models import LogEventType

JsonObject: TypeAlias = dict[str, JsonValue]


class CliLogEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int
    event_id: str = Field(alias="id")
    run_id: str
    event_type: LogEventType = Field(alias="type")
    step_id: str | None = None
    step_type: str | None = None
    agent_sequence: int | None = None
    created_at: str
    payload: JsonObject
