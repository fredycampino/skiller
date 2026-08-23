CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
CODEX_TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_USER_AGENT = "codex_cli_rs/0.0.0 (Skiller)"
CODEX_ORIGINATOR = "codex_cli_rs"
CODEX_AUTH_USER_AGENT = "skiller-openai-auth/0.1"
CODEX_TOKEN_EXPIRY_SKEW_SECONDS = 60


def codex_headers(account_id: str | None) -> dict[str, str]:
    headers = {
        "User-Agent": CODEX_USER_AGENT,
        "originator": CODEX_ORIGINATOR,
    }
    if account_id is not None:
        headers["ChatGPT-Account-ID"] = account_id
    return headers


def _load_openai_client_class() -> type[object]:
    from openai import OpenAI  # type: ignore[import-not-found]

    return OpenAI
