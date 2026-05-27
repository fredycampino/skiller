#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
ISSUER_URL = "https://auth.openai.com"
DEVICE_CODE_URL = f"{ISSUER_URL}/api/accounts/deviceauth/usercode"
DEVICE_TOKEN_URL = f"{ISSUER_URL}/api/accounts/deviceauth/token"
DEVICE_VERIFICATION_URL = f"{ISSUER_URL}/codex/device"
DEVICE_REDIRECT_URI = f"{ISSUER_URL}/deviceauth/callback"
TOKEN_URL = f"{ISSUER_URL}/oauth/token"
CODEX_RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_TIMEOUT_SECONDS = 15 * 60
USER_AGENT = "skiller-codex-auth/0.1"
CODEX_USER_AGENT = "codex_cli_rs/0.0.0 (Skiller)"
VERIFY_MARKER = "skiller-openai-codex-ok"


class AuthError(Exception):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="OpenAI Codex device authentication and credential verification for Skiller."
    )
    parser.add_argument(
        "--credentials-file",
        default=os.environ.get(
            "SKILLER_OPENAI_CODEX_CREDENTIALS_FILE",
            str(default_credentials_file()),
        ),
        help="Credentials path. Default: %(default)s",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "request-device-code",
        help="Request an OpenAI device code and print the verification URL.",
    )
    subparsers.add_parser("user-code", help="Print the pending user code.")

    poll_parser = subparsers.add_parser(
        "poll-device-auth",
        help="Poll until OpenAI returns an authorization code.",
    )
    poll_parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)

    subparsers.add_parser(
        "exchange-token",
        help="Exchange the pending authorization code and save credentials.",
    )

    status_parser = subparsers.add_parser("status", help="Show credential status.")
    status_parser.add_argument("--require", action="store_true")

    verify_parser = subparsers.add_parser("verify", help="Verify saved credentials.")
    verify_parser.add_argument(
        "--model",
        default=os.environ.get("SKILLER_OPENAI_CODEX_MODEL", DEFAULT_MODEL),
    )

    args = parser.parse_args()

    try:
        credentials_file = Path(args.credentials_file).expanduser()
        if args.command == "request-device-code":
            request_device_code(credentials_file=credentials_file)
        elif args.command == "user-code":
            print_user_code(credentials_file=credentials_file)
        elif args.command == "poll-device-auth":
            poll_device_auth(
                credentials_file=credentials_file,
                timeout_seconds=args.timeout_seconds,
            )
        elif args.command == "exchange-token":
            exchange_token(credentials_file=credentials_file)
        elif args.command == "status":
            show_status(credentials_file=credentials_file, require=args.require)
        elif args.command == "verify":
            verify_credentials(credentials_file=credentials_file, model=args.model)
        else:
            raise AuthError(f"unsupported command: {args.command}")
    except AuthError as exc:
        print(f"error: {exc}", file=os.sys.stderr)
        return 1
    return 0


def request_device_code(*, credentials_file: Path) -> None:
    response = post_json(
        DEVICE_CODE_URL,
        {"client_id": CLIENT_ID},
        headers={},
    )
    user_code = required_str(response, "user_code")
    device_auth_id = required_str(response, "device_auth_id")
    interval = optional_int(response, "interval") or 5
    expires_in = optional_int(response, "expires_in")
    pending_payload = {
        "client_id": CLIENT_ID,
        "device_auth_id": device_auth_id,
        "user_code": user_code,
        "verification_url": DEVICE_VERIFICATION_URL,
        "interval": max(3, interval),
        "created_at": int(time.time()),
    }
    if expires_in is not None:
        pending_payload["expires_at"] = int(time.time()) + expires_in
    write_json(pending_file(credentials_file), pending_payload)
    print(DEVICE_VERIFICATION_URL)


def print_user_code(*, credentials_file: Path) -> None:
    pending_payload = read_pending(credentials_file)
    print(required_str(pending_payload, "user_code"))


def poll_device_auth(*, credentials_file: Path, timeout_seconds: int) -> None:
    pending_payload = read_pending(credentials_file)
    device_auth_id = required_str(pending_payload, "device_auth_id")
    user_code = required_str(pending_payload, "user_code")
    interval = optional_int(pending_payload, "interval") or 5
    deadline = resolve_poll_deadline(pending_payload, timeout_seconds=timeout_seconds)

    while time.time() < deadline:
        time.sleep(max(3, interval))
        response = poll_device_token(
            device_auth_id=device_auth_id,
            user_code=user_code,
        )
        if response is None:
            continue

        authorization_code = required_str(response, "authorization_code")
        code_verifier = required_str(response, "code_verifier")
        pending_payload["authorization_code"] = authorization_code
        pending_payload["code_verifier"] = code_verifier
        pending_payload["authorized_at"] = int(time.time())
        write_json(pending_file(credentials_file), pending_payload)
        print("OpenAI Codex device authorization completed.")
        return

    raise AuthError("device authorization timed out")


def poll_device_token(*, device_auth_id: str, user_code: str) -> dict[str, Any] | None:
    request = build_json_request(
        DEVICE_TOKEN_URL,
        {
            "device_auth_id": device_auth_id,
            "user_code": user_code,
        },
        headers={},
    )
    try:
        return read_http_json(request)
    except HttpStatusError as exc:
        if exc.status_code in {403, 404}:
            return None
        raise AuthError(f"device authorization failed: HTTP {exc.status_code}: {exc.body}") from exc


def exchange_token(*, credentials_file: Path) -> None:
    pending_payload = read_pending(credentials_file)
    authorization_code = required_str(pending_payload, "authorization_code")
    code_verifier = required_str(pending_payload, "code_verifier")
    token_response = exchange_authorization_code(
        code=authorization_code,
        code_verifier=code_verifier,
    )
    save_credentials(
        credentials_file=credentials_file,
        token_response=token_response,
        pending_payload=pending_payload,
    )
    pending_file(credentials_file).unlink(missing_ok=True)
    print("OpenAI Codex credentials saved.")


def show_status(*, credentials_file: Path, require: bool) -> None:
    if credentials_file.exists():
        credentials = read_json(credentials_file)
        required_str(credentials, "access_token")
        print("OpenAI Codex credentials are saved.")
        print(f"Credentials file: {credentials_file}")
        return

    message = f"OpenAI Codex credentials are not saved yet: {credentials_file}"
    if require:
        raise AuthError(message)
    print(message)


def verify_credentials(*, credentials_file: Path, model: str) -> None:
    credentials = read_json(credentials_file)
    access_token = required_str(credentials, "access_token")
    payload = {
        "model": model,
        "instructions": (
            "You are a credential validation probe. "
            "Reply only with the requested marker."
        ),
        "input": [
            {
                "role": "user",
                "content": f"Reply with exactly: {VERIFY_MARKER}",
            }
        ],
        "store": False,
        "stream": True,
    }
    response_text = post_codex_stream(access_token=access_token, payload=payload)
    if VERIFY_MARKER not in response_text:
        raise AuthError("credential verification did not return expected marker")
    print(f"skiller-openai-codex-ok ({model})")


def exchange_authorization_code(*, code: str, code_verifier: str) -> dict[str, Any]:
    return post_form(
        TOKEN_URL,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": DEVICE_REDIRECT_URI,
            "client_id": CLIENT_ID,
            "code_verifier": code_verifier,
        },
    )


def save_credentials(
    *,
    credentials_file: Path,
    token_response: dict[str, Any],
    pending_payload: dict[str, Any],
) -> None:
    required_str(token_response, "access_token")
    payload = dict(token_response)
    payload.update(
        {
            "auth_mode": "chatgpt",
            "client_id": CLIENT_ID,
            "redirect_uri": DEVICE_REDIRECT_URI,
            "created_at": int(time.time()),
            "source": "skiller-codex-auth",
            "device_auth_hash": hashlib.sha256(
                required_str(pending_payload, "device_auth_id").encode("utf-8")
            ).hexdigest(),
        }
    )
    expires_in = optional_int(token_response, "expires_in")
    if expires_in is not None:
        payload["expires_at"] = int(time.time()) + expires_in
    write_json(credentials_file, payload)


def resolve_poll_deadline(
    pending_payload: dict[str, Any],
    *,
    timeout_seconds: int,
) -> float:
    timeout_deadline = time.time() + max(1, timeout_seconds)
    expires_at = optional_int(pending_payload, "expires_at")
    if expires_at is None:
        return timeout_deadline
    return min(timeout_deadline, float(expires_at))


def post_json(url: str, payload: dict[str, Any], *, headers: dict[str, str]) -> dict[str, Any]:
    try:
        return read_http_json(build_json_request(url, payload, headers=headers))
    except HttpStatusError as exc:
        raise AuthError(f"HTTP {exc.status_code}: {exc.body}") from exc


def post_codex_stream(*, access_token: str, payload: dict[str, Any]) -> str:
    request = build_json_request(
        CODEX_RESPONSES_URL,
        payload,
        headers=codex_response_headers(access_token),
    )
    text_parts: list[str] = []
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data: "):
                    continue
                event_payload = parse_json_object(line.removeprefix("data: ").strip())
                if event_payload is None:
                    continue
                if event_payload.get("type") == "response.output_text.delta":
                    delta = event_payload.get("delta")
                    if isinstance(delta, str):
                        text_parts.append(delta)
                if event_payload.get("type") == "response.completed":
                    break
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise AuthError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise AuthError(f"request failed: {exc.reason}") from exc
    return "".join(text_parts)


def codex_response_headers(access_token: str) -> dict[str, str]:
    headers = {
        "Accept": "text/event-stream",
        "Authorization": f"Bearer {access_token}",
        "User-Agent": CODEX_USER_AGENT,
        "originator": "codex_cli_rs",
    }
    account_id = extract_chatgpt_account_id(access_token)
    if account_id:
        headers["ChatGPT-Account-ID"] = account_id
    return headers


def extract_chatgpt_account_id(access_token: str) -> str | None:
    parts = access_token.split(".")
    if len(parts) < 2:
        return None
    payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload_b64))
    except (ValueError, json.JSONDecodeError):
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


def parse_json_object(raw_payload: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def build_json_request(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str],
) -> urllib.request.Request:
    request_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        **headers,
    }
    return urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )


def post_form(url: str, payload: dict[str, str]) -> dict[str, Any]:
    body = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        return read_http_json(request)
    except HttpStatusError as exc:
        raise AuthError(f"HTTP {exc.status_code}: {exc.body}") from exc


def read_http_json(request: urllib.request.Request) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise HttpStatusError(status_code=exc.code, body=body) from exc
    except urllib.error.URLError as exc:
        raise AuthError(f"request failed: {exc.reason}") from exc

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise AuthError("response must be JSON") from exc
    if not isinstance(payload, dict):
        raise AuthError("response must contain a JSON object")
    return payload


def read_pending(credentials_file: Path) -> dict[str, Any]:
    return read_json(pending_file(credentials_file))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AuthError(f"file does not exist: {path}")
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise AuthError(f"file must contain a JSON object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, sort_keys=True)
        file.write("\n")
    temp_path.replace(path)
    path.chmod(0o600)


def required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AuthError(f"missing field: {key}")
    return value.strip()


def optional_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise AuthError(f"field must be an integer: {key}")


def default_credentials_file() -> Path:
    return Path.home() / ".skiller" / "secrets" / "openai-codex.json"


def pending_file(credentials_file: Path) -> Path:
    return credentials_file.with_name("openai-codex.pending.json")


class HttpStatusError(Exception):
    def __init__(self, *, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"HTTP {status_code}: {body}")


if __name__ == "__main__":
    raise SystemExit(main())
