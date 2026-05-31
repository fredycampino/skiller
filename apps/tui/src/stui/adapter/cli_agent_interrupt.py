from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict


class CliAgentInterruptEnqueued(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: Literal["ENQUEUED"]
    enqueued: Literal[True]
    item: dict[str, object] | None = None


class CliAgentInterruptRejected(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: Literal["INVALID_RUN_ID", "RUN_NOT_FOUND"]
    enqueued: Literal[False]
    error: str


CliAgentInterrupt: TypeAlias = (
    CliAgentInterruptEnqueued | CliAgentInterruptRejected
)
