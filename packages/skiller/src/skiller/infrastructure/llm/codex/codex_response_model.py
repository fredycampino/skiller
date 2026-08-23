from __future__ import annotations

from dataclasses import dataclass

from openai.types.responses import Response, ResponsesServerEvent


@dataclass(frozen=True)
class CodexResponseModel:
    response: Response
    stream: tuple[ResponsesServerEvent, ...]
