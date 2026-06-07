from __future__ import annotations

import base64
import binascii
import json
import time
from dataclasses import dataclass
from pathlib import Path


class CodexCredentialsError(Exception):
    pass


@dataclass(frozen=True)
class CodexCredentials:
    access_token: str
    auth_mode: str
    client_id: str
    created_at: int
    expires_at: int
    expires_in: int
    id_token: str
    redirect_uri: str
    refresh_token: str
    scope: str
    source: str
    token_type: str

    @property
    def account_id(self) -> str | None:
        return _account_id_from_token(self.access_token)


class CodexCredentialsDatasource:
    def load(self, credentials_file: str) -> CodexCredentials:
        path = Path(credentials_file).expanduser()
        if not path.exists():
            raise CodexCredentialsError(f"Missing Codex credentials file: {path}")

        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, dict):
            raise CodexCredentialsError("Codex credentials file must contain a JSON object")

        access_token = _required_text(payload.get("access_token"), "access_token")
        return CodexCredentials(
            access_token=access_token,
            auth_mode=_required_text(payload.get("auth_mode"), "auth_mode"),
            client_id=_required_text(payload.get("client_id"), "client_id"),
            created_at=_required_int(payload.get("created_at"), "created_at"),
            expires_at=_required_int(payload.get("expires_at"), "expires_at"),
            expires_in=_required_int(payload.get("expires_in"), "expires_in"),
            id_token=_required_text(payload.get("id_token"), "id_token"),
            redirect_uri=_required_text(payload.get("redirect_uri"), "redirect_uri"),
            refresh_token=_required_text(payload.get("refresh_token"), "refresh_token"),
            scope=_required_text(payload.get("scope"), "scope"),
            source=_required_text(payload.get("source"), "source"),
            token_type=_required_text(payload.get("token_type"), "token_type"),
        )

    def refresh(
        self,
        credentials_file: str,
        token_response: dict[str, object],
    ) -> CodexCredentials:
        credentials = self.load(credentials_file)
        access_token = _required_text(token_response.get("access_token"), "access_token")
        refresh_token = credentials.refresh_token
        raw_refresh_token = token_response.get("refresh_token")
        if isinstance(raw_refresh_token, str) and raw_refresh_token.strip():
            refresh_token = raw_refresh_token.strip()

        expires_in = credentials.expires_in
        raw_expires_in = token_response.get("expires_in")
        if (
            isinstance(raw_expires_in, int)
            and not isinstance(raw_expires_in, bool)
            and raw_expires_in > 0
        ):
            expires_in = raw_expires_in
        expires_at = int(time.time()) + expires_in

        id_token = credentials.id_token
        raw_id_token = token_response.get("id_token")
        if isinstance(raw_id_token, str) and raw_id_token.strip():
            id_token = raw_id_token.strip()

        token_type = credentials.token_type
        raw_token_type = token_response.get("token_type")
        if isinstance(raw_token_type, str) and raw_token_type.strip():
            token_type = raw_token_type.strip()

        scope = credentials.scope
        raw_scope = token_response.get("scope")
        if isinstance(raw_scope, str) and raw_scope.strip():
            scope = raw_scope.strip()

        refreshed_credentials = CodexCredentials(
            access_token=access_token,
            auth_mode=credentials.auth_mode,
            client_id=credentials.client_id,
            created_at=credentials.created_at,
            expires_at=expires_at,
            expires_in=expires_in,
            id_token=id_token,
            redirect_uri=credentials.redirect_uri,
            refresh_token=refresh_token,
            scope=scope,
            source=credentials.source,
            token_type=token_type,
        )

        path = Path(credentials_file).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = _load_json_object(path)
        payload.update(
            {
                "access_token": refreshed_credentials.access_token,
                "auth_mode": refreshed_credentials.auth_mode,
                "client_id": refreshed_credentials.client_id,
                "created_at": refreshed_credentials.created_at,
                "expires_at": refreshed_credentials.expires_at,
                "expires_in": refreshed_credentials.expires_in,
                "id_token": refreshed_credentials.id_token,
                "redirect_uri": refreshed_credentials.redirect_uri,
                "refresh_token": refreshed_credentials.refresh_token,
                "scope": refreshed_credentials.scope,
                "source": refreshed_credentials.source,
                "token_type": refreshed_credentials.token_type,
            }
        )
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, sort_keys=True)
            file.write("\n")
        path.chmod(0o600)
        return refreshed_credentials


def _required_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CodexCredentialsError(f"Codex credentials require {name}")
    return value.strip()


def _required_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CodexCredentialsError(f"Codex credentials require {name}")
    return value


def _load_json_object(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise CodexCredentialsError("Codex credentials file must contain a JSON object")
    return payload


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
