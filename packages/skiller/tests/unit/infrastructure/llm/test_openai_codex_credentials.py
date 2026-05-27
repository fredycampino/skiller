from __future__ import annotations

import base64
import json

import pytest

from skiller.infrastructure.llm.openai_codex_credentials import (
    OpenAICodexCredentials,
    OpenAICodexCredentialsError,
    OpenAICodexCredentialsLoader,
)

pytestmark = pytest.mark.unit


def test_openai_codex_credentials_loader_reads_access_token_and_account_id(tmp_path) -> None:
    credentials_file = tmp_path / "openai-codex.json"
    credentials_file.write_text(
        json.dumps(
            {
                "access_token": "token",
                "account_id": "account-1",
            }
        ),
        encoding="utf-8",
    )

    credentials = OpenAICodexCredentialsLoader().load(str(credentials_file))

    assert credentials == OpenAICodexCredentials(
        access_token="token",
        account_id="account-1",
    )


def test_openai_codex_credentials_loader_extracts_account_id_from_token(tmp_path) -> None:
    credentials_file = tmp_path / "openai-codex.json"
    token = _token_with_claims(
        {
            "https://api.openai.com/auth": {
                "chatgpt_account_id": "account-from-token",
            }
        }
    )
    credentials_file.write_text(
        json.dumps(
            {
                "access_token": token,
            }
        ),
        encoding="utf-8",
    )

    credentials = OpenAICodexCredentialsLoader().load(str(credentials_file))

    assert credentials == OpenAICodexCredentials(
        access_token=token,
        account_id="account-from-token",
    )


def test_openai_codex_credentials_loader_rejects_missing_access_token(tmp_path) -> None:
    credentials_file = tmp_path / "openai-codex.json"
    credentials_file.write_text("{}", encoding="utf-8")

    with pytest.raises(OpenAICodexCredentialsError, match="access_token"):
        OpenAICodexCredentialsLoader().load(str(credentials_file))


def _token_with_claims(claims: dict[str, object]) -> str:
    payload = json.dumps(claims).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"header.{encoded}.signature"
