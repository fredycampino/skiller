from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from pathlib import Path


class OpenAICodexCredentialsError(Exception):
    pass


@dataclass(frozen=True)
class OpenAICodexCredentials:
    access_token: str
    account_id: str | None


class OpenAICodexCredentialsLoader:
    def load(self, credentials_file: str) -> OpenAICodexCredentials:
        path = Path(credentials_file).expanduser()
        if not path.exists():
            raise OpenAICodexCredentialsError(f"Missing Codex credentials file: {path}")

        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, dict):
            raise OpenAICodexCredentialsError("Codex credentials file must contain a JSON object")

        access_token = _required_text(payload.get("access_token"), "access_token")
        account_id = _optional_text(payload.get("account_id"))
        if account_id is None:
            account_id = _account_id_from_token(access_token)

        return OpenAICodexCredentials(
            access_token=access_token,
            account_id=account_id,
        )


def _required_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OpenAICodexCredentialsError(f"Codex credentials require {name}")
    return value.strip()


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _account_id_from_token(access_token: str) -> str | None:
    parts = access_token.split(".")
    if len(parts) < 2:
        return None

    payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload_b64))
    except (binascii.Error, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(claims, dict):
        return None

    auth_claims = claims.get("https://api.openai.com/auth")
    if not isinstance(auth_claims, dict):
        return None

    account_id = auth_claims.get("chatgpt_account_id")
    if not isinstance(account_id, str) or not account_id.strip():
        return None
    return account_id.strip()
