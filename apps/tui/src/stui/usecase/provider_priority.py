from __future__ import annotations

_PROVIDER_PRIORITY = (
    "codex",
    "bedrock",
    "ollama",
    "lmstudio",
    "openrouter",
    "deepseek",
    "moonshot",
    "minimax",
)


def provider_priority(name: str) -> int:
    """Keep additional providers after the preferred providers in their original order."""
    if name in _PROVIDER_PRIORITY:
        return _PROVIDER_PRIORITY.index(name)
    return len(_PROVIDER_PRIORITY)
