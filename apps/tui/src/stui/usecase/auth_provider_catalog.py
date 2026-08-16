from __future__ import annotations

AUTH_PROVIDER_RUN_ARGS = {
    "moonshot": "auths/moonshot",
    "codex": "auths/codex",
    "bedrock": "auths/bedrock",
    "minimax": "auths/minimax",
    "lmstudio": "auths/lmstudio",
}


def auth_provider_names() -> tuple[str, ...]:
    return tuple(AUTH_PROVIDER_RUN_ARGS)
