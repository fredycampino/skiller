import json

from skiller.domain.agent.context.model import (
    AgentContextPayload,
    agent_context_payload_to_dict,
)

AGENT_CONTEXT_DELTA_TOKEN_CHAR_DIVISOR = 3


def estimate_delta_tokens_from_chars(
    *,
    block_chars: int,
) -> int:
    if block_chars <= 0:
        return 0

    delta_tokens = (
        block_chars + AGENT_CONTEXT_DELTA_TOKEN_CHAR_DIVISOR // 2
    ) // AGENT_CONTEXT_DELTA_TOKEN_CHAR_DIVISOR
    return max(1, delta_tokens)


def payload_chars(payload: AgentContextPayload) -> int:
    return len(json.dumps(agent_context_payload_to_dict(payload), sort_keys=True))
