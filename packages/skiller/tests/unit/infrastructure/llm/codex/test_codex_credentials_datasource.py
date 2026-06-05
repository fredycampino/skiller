from __future__ import annotations

import base64
import json

import pytest

from skiller.infrastructure.llm.codex import codex_credentials_datasource
from skiller.infrastructure.llm.codex.codex_credentials_datasource import (
    CodexCredentials,
    CodexCredentialsDatasource,
    CodexCredentialsError,
)

pytestmark = pytest.mark.unit


def test_codex_credentials_datasource_reads_credentials(tmp_path) -> None:
    credentials_file = tmp_path / "openai-codex.json"
    token = _token_with_claims(
        {
            "https://api.openai.com/auth": {
                "chatgpt_account_id": "account-1",
            }
        }
    )
    credentials_file.write_text(
        json.dumps(_credentials_payload(access_token=token)),
        encoding="utf-8",
    )

    credentials = CodexCredentialsDatasource().load(str(credentials_file))

    assert credentials == CodexCredentials(
        access_token=token,
        auth_mode="chatgpt",
        client_id="app_EMoamEEZ73f0CkXaXp7hrann",
        created_at=1779742890,
        device_auth_hash="70c",
        expires_at=1780606889,
        expires_in=863999,
        id_token="id-token",
        redirect_uri="https://auth.openai.com/deviceauth/callback",
        refresh_token="refresh-token",
        scope="openid profile email offline_access",
        source="skiller-codex-auth",
        token_type="bearer",
    )
    assert credentials.account_id == "account-1"


def test_codex_credentials_datasource_refreshes_credentials(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credentials_file = tmp_path / "openai-codex.json"
    credentials_file.write_text(
        json.dumps(_credentials_payload(access_token="old-token")),
        encoding="utf-8",
    )
    monkeypatch.setattr(codex_credentials_datasource.time, "time", lambda: 1000)

    credentials = CodexCredentialsDatasource().refresh(
        str(credentials_file),
        {
            "access_token": "new-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 600,
            "id_token": "new-id-token",
            "token_type": "bearer",
            "scope": "openid profile email offline_access",
        },
    )

    payload = json.loads(credentials_file.read_text(encoding="utf-8"))
    assert credentials.access_token == "new-token"
    assert credentials.refresh_token == "new-refresh-token"
    assert credentials.expires_in == 600
    assert credentials.expires_at == 1600
    assert credentials.id_token == "new-id-token"
    assert payload["access_token"] == "new-token"
    assert payload["refresh_token"] == "new-refresh-token"
    assert payload["expires_in"] == 600
    assert payload["expires_at"] == 1600
    assert payload["id_token"] == "new-id-token"
    assert payload["client_id"] == "app_EMoamEEZ73f0CkXaXp7hrann"
    assert credentials_file.stat().st_mode & 0o777 == 0o600


def test_codex_credentials_datasource_extracts_account_id_from_token(tmp_path) -> None:
    credentials_file = tmp_path / "openai-codex.json"
    token = _token_with_claims(
        {
            "https://api.openai.com/auth": {
                "chatgpt_account_id": "account-from-token",
            }
        }
    )
    credentials_file.write_text(
        json.dumps(_credentials_payload(access_token=token)),
        encoding="utf-8",
    )

    credentials = CodexCredentialsDatasource().load(str(credentials_file))

    assert credentials.account_id == "account-from-token"


def test_codex_credentials_datasource_rejects_missing_access_token(tmp_path) -> None:
    credentials_file = tmp_path / "openai-codex.json"
    credentials_file.write_text("{}", encoding="utf-8")

    with pytest.raises(CodexCredentialsError, match="access_token"):
        CodexCredentialsDatasource().load(str(credentials_file))


def _credentials_payload(*, access_token: str) -> dict[str, object]:
    return {
        "access_token": access_token,
        "auth_mode": "chatgpt",
        "client_id": "app_EMoamEEZ73f0CkXaXp7hrann",
        "created_at": 1779742890,
        "device_auth_hash": "70c",
        "expires_at": 1780606889,
        "expires_in": 863999,
        "id_token": "id-token",
        "redirect_uri": "https://auth.openai.com/deviceauth/callback",
        "refresh_token": "refresh-token",
        "scope": "openid profile email offline_access",
        "source": "skiller-codex-auth",
        "token_type": "bearer",
    }


def _token_with_claims(claims: dict[str, object]) -> str:
    payload = json.dumps(claims).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"header.{encoded}.signature"
