import json

from skiller.domain.agent.context.model import (
    AgentAssistantMessagePayload,
    AgentAssistantMessageType,
    AgentContextPayload,
    AgentToolCallPayload,
    AgentToolResultPayload,
    agent_context_payload_to_dict,
)

AGENT_CONTEXT_COMPACT_DELTA_MIN_DIVISOR = 3


def compact_delta_tokens(
    *,
    delta_tokens: int,
    payloads: list[AgentContextPayload],
) -> int:
    if delta_tokens == 0:
        return 0
    if not any(_is_prunable_payload(item) for item in payloads):
        return delta_tokens

    full_chars = sum(_payload_chars(item) for item in payloads)
    if full_chars <= 0:
        return delta_tokens

    compact_chars = sum(
        _payload_chars(item)
        for item in payloads
        if not _is_prunable_payload(item)
    )
    compact_tokens = round(delta_tokens * compact_chars / full_chars)
    return min(delta_tokens, compact_tokens)


def legacy_compact_delta_tokens(*, delta_tokens: int) -> int:
    if delta_tokens == 0:
        return 0
    return _minimum_compact_tokens(delta_tokens)


def _minimum_compact_tokens(delta_tokens: int) -> int:
    return (
        delta_tokens + AGENT_CONTEXT_COMPACT_DELTA_MIN_DIVISOR - 1
    ) // AGENT_CONTEXT_COMPACT_DELTA_MIN_DIVISOR


def _is_prunable_payload(payload: AgentContextPayload) -> bool:
    if isinstance(payload, AgentToolCallPayload | AgentToolResultPayload):
        return True
    if not isinstance(payload, AgentAssistantMessagePayload):
        return False
    return payload.message_type == AgentAssistantMessageType.TOOL_CALLS


def _payload_chars(payload: AgentContextPayload) -> int:
    return len(json.dumps(agent_context_payload_to_dict(payload), sort_keys=True))
