from __future__ import annotations

import copy
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field

from skiller.domain.agent.llm.model import LLMToolMessage, LLMUserMessage
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest

CODEX_TURN_STATE_HEADER = "x-codex-turn-state"


@dataclass(frozen=True)
class CodexTurnIdentity:
    installation_id: str
    session_id: str
    thread_id: str
    window_id: str
    turn_id: str
    turn_started_at_unix_ms: int


@dataclass
class CodexTurnSession:
    model: str
    identity: CodexTurnIdentity
    turn_state: str | None = None
    response_output_batches: list[tuple[dict[str, object], ...]] = field(
        default_factory=list
    )

    def record_turn_state(self, turn_state: str | None) -> None:
        if turn_state is not None:
            self.turn_state = turn_state

    def record_output_items(self, output_items: tuple[object, ...]) -> None:
        mapped_items: list[dict[str, object]] = []
        for output_item in output_items:
            mapped_item = _external_object_to_dict(output_item)
            if mapped_item:
                mapped_items.append(mapped_item)
        if mapped_items:
            self.response_output_batches.append(tuple(mapped_items))


class CodexTurnSessionManager:
    def __init__(self) -> None:
        self.installation_id = str(uuid.uuid4())
        self.window_id = str(uuid.uuid4())
        self.sessions: dict[str, CodexTurnSession] = {}

    def resolve(self, request: CodexLLMRequest) -> CodexTurnSession:
        existing = self.sessions.get(request.session_id)
        is_continuation = _is_tool_continuation(request)
        is_same_model = existing is not None and existing.model == request.model.value
        if is_continuation and is_same_model:
            return existing

        identity = CodexTurnIdentity(
            installation_id=self.installation_id,
            session_id=request.session_id,
            thread_id=request.session_id,
            window_id=self.window_id,
            turn_id=str(uuid.uuid4()),
            turn_started_at_unix_ms=int(time.time() * 1000),
        )
        session = CodexTurnSession(
            model=request.model.value,
            identity=identity,
        )
        self.sessions[request.session_id] = session
        return session

    def finish(self, session: CodexTurnSession) -> None:
        current = self.sessions.get(session.identity.session_id)
        if current is session:
            self.sessions.pop(session.identity.session_id)


def _is_tool_continuation(request: CodexLLMRequest) -> bool:
    last_user_index = -1
    for index, message in enumerate(request.messages):
        if isinstance(message, LLMUserMessage):
            last_user_index = index

    return any(
        isinstance(message, LLMToolMessage)
        for message in request.messages[last_user_index + 1 :]
    )


def _external_object_to_dict(value: object) -> dict[str, object]:
    if isinstance(value, Mapping):
        return copy.deepcopy(dict(value))
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        mapped = model_dump(mode="json", exclude_none=True)
        if isinstance(mapped, dict):
            return mapped
    return {}
