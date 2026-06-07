#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import http.server
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
REDIRECT_URI = "http://localhost:1455/auth/callback"
CALLBACK_HOST = "localhost"
CALLBACK_PORT = 1455
SCOPE = "openid profile email offline_access"
CODEX_RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_TIMEOUT_SECONDS = 15 * 60
USER_AGENT = "skiller-openai-auth/0.1"
CODEX_USER_AGENT = "pi (skiller)"
VERIFY_MARKER = "skiller-openai-codex-ok"


class AuthError(Exception):
    pass


class HttpStatusError(Exception):
    def __init__(self, *, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"HTTP {status_code}: {body}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="OpenAI Codex local-callback authentication for Skiller."
    )
    parser.add_argument(
        "--credentials-file",
        default=str(default_credentials_file()),
        help="Credentials path. Default: %(default)s",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("credentials-file", help="Print the resolved credentials file path.")
    subparsers.add_parser("prepare", help="Prepare authorization and print the URL.")
    subparsers.add_parser(
        "start-callback-server",
        help="Start the local OAuth callback server in the background.",
    )

    serve_parser = subparsers.add_parser(
        "serve-callback-server",
        help=argparse.SUPPRESS,
    )
    serve_parser.add_argument("--ready-file", required=True)
    serve_parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)

    wait_parser = subparsers.add_parser("wait-callback", help="Wait for local callback.")
    wait_parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)

    subparsers.add_parser("exchange-token", help="Exchange code and save credentials.")

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
        if args.command == "credentials-file":
            print(credentials_file)
        elif args.command == "prepare":
            prepare_authorization(credentials_file=credentials_file)
        elif args.command == "start-callback-server":
            start_callback_server(credentials_file=credentials_file)
        elif args.command == "serve-callback-server":
            serve_callback_server(
                credentials_file=credentials_file,
                ready_file=Path(args.ready_file).expanduser(),
                timeout_seconds=args.timeout_seconds,
            )
        elif args.command == "wait-callback":
            wait_callback(credentials_file=credentials_file, timeout_seconds=args.timeout_seconds)
        elif args.command == "exchange-token":
            exchange_token(credentials_file=credentials_file)
        elif args.command == "status":
            show_status(credentials_file=credentials_file, require=args.require)
        elif args.command == "verify":
            verify_credentials(credentials_file=credentials_file, model=args.model)
        else:
            raise AuthError(f"unsupported command: {args.command}")
    except AuthError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def prepare_authorization(*, credentials_file: Path) -> None:
    state = secrets.token_urlsafe(24)
    verifier = token_urlsafe(64)
    challenge = code_challenge(verifier)
    authorization_url = build_authorization_url(state=state, challenge=challenge)
    pending_payload = {
        "state": state,
        "code_verifier": verifier,
        "redirect_uri": REDIRECT_URI,
        "authorization_url": authorization_url,
        "credentials_file": str(credentials_file),
        "created_at": int(time.time()),
    }
    write_json(pending_file(credentials_file), pending_payload)
    callback_file(credentials_file).unlink(missing_ok=True)
    server_file(credentials_file).unlink(missing_ok=True)
    server_ready_file(credentials_file).unlink(missing_ok=True)
    server_log_file(credentials_file).unlink(missing_ok=True)
    print(authorization_url)


def start_callback_server(*, credentials_file: Path) -> None:
    pending_payload = read_pending(credentials_file)
    required_str(pending_payload, "state")

    ready_file = server_ready_file(credentials_file)
    ready_file.unlink(missing_ok=True)
    log_file = server_log_file(credentials_file)
    log_file.unlink(missing_ok=True)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--credentials-file",
        str(credentials_file),
        "serve-callback-server",
        "--ready-file",
        str(ready_file),
        "--timeout-seconds",
        str(DEFAULT_TIMEOUT_SECONDS),
    ]
    with log_file.open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    deadline = time.time() + 5
    while time.time() < deadline:
        if ready_file.exists():
            write_json(
                server_file(credentials_file),
                {
                    "pid": process.pid,
                    "callback_url": REDIRECT_URI,
                    "created_at": int(time.time()),
                    "log_file": str(log_file),
                },
            )
            print(REDIRECT_URI)
            return
        if process.poll() is not None:
            raise AuthError(read_server_log(log_file))
        time.sleep(0.1)

    process.terminate()
    raise AuthError("callback server did not become ready")


def serve_callback_server(
    *,
    credentials_file: Path,
    ready_file: Path,
    timeout_seconds: int,
) -> None:
    pending_payload = read_pending(credentials_file)
    expected_state = required_str(pending_payload, "state")
    callback_payload_file = callback_file(credentials_file)

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed_url = urllib.parse.urlparse(self.path)
            if parsed_url.path != "/auth/callback":
                self._send_html(404, oauth_error_html("Callback route not found."))
                return

            params = urllib.parse.parse_qs(parsed_url.query)
            state = first_param(params, "state")
            code = first_param(params, "code")
            if state != expected_state:
                write_json(callback_payload_file, {"error": "state mismatch"})
                self._send_html(400, oauth_error_html("State mismatch."))
                return
            if not code:
                write_json(callback_payload_file, {"error": "missing authorization code"})
                self._send_html(400, oauth_error_html("Missing authorization code."))
                return

            payload = dict(read_pending(credentials_file))
            payload["authorization_code"] = code
            payload["callback_received_at"] = int(time.time())
            write_json(pending_file(credentials_file), payload)
            write_json(callback_payload_file, {"status": "received"})
            self._send_html(
                200,
                oauth_success_html("OpenAI authentication completed. You can close this window."),
            )

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _send_html(self, status: int, body: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

    try:
        server = http.server.ThreadingHTTPServer(
            (CALLBACK_HOST, CALLBACK_PORT),
            CallbackHandler,
        )
    except OSError as exc:
        raise AuthError(f"failed to bind {REDIRECT_URI}: {exc}") from exc

    server.timeout = 1
    write_text_file(ready_file, "ready\n")
    deadline = time.time() + max(1, timeout_seconds)
    try:
        while time.time() < deadline:
            if callback_payload_file.exists():
                payload = read_json(callback_payload_file)
                if payload.get("status") == "received":
                    return
                if isinstance(payload.get("error"), str):
                    return
            server.handle_request()
    finally:
        server.server_close()


def wait_callback(*, credentials_file: Path, timeout_seconds: int) -> None:
    deadline = time.time() + max(1, timeout_seconds)
    while time.time() < deadline:
        pending_payload = read_pending(credentials_file)
        authorization_code = pending_payload.get("authorization_code")
        if isinstance(authorization_code, str) and authorization_code.strip():
            print("OpenAI authorization callback received.")
            return

        payload_file = callback_file(credentials_file)
        if payload_file.exists():
            payload = read_json(payload_file)
            error = payload.get("error")
            if isinstance(error, str) and error:
                raise AuthError(error)
        time.sleep(1)

    raise AuthError("authorization callback timed out")


def exchange_token(*, credentials_file: Path) -> None:
    pending_payload = read_pending(credentials_file)
    authorization_code = required_str(pending_payload, "authorization_code")
    verifier = required_str(pending_payload, "code_verifier")
    token_response = exchange_authorization_code(
        code=authorization_code,
        verifier=verifier,
    )
    save_credentials(
        credentials_file=credentials_file,
        token_response=token_response,
        pending_payload=pending_payload,
    )
    cleanup_authorization_files(credentials_file)
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
    account_id = required_str(credentials, "account_id")
    payload = {
        "model": model,
        "store": False,
        "stream": True,
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
        "text": {"verbosity": "low"},
        "include": ["reasoning.encrypted_content"],
        "tool_choice": "auto",
        "parallel_tool_calls": True,
    }
    response_text = post_codex_stream(
        access_token=access_token,
        account_id=account_id,
        payload=payload,
    )
    if VERIFY_MARKER not in response_text:
        raise AuthError("credential verification did not return expected marker")
    print(f"{VERIFY_MARKER} ({model})")


def build_authorization_url(*, state: str, challenge: str) -> str:
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "originator": "pi",
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def exchange_authorization_code(*, code: str, verifier: str) -> dict[str, Any]:
    return post_form(
        TOKEN_URL,
        {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": REDIRECT_URI,
        },
    )


def save_credentials(
    *,
    credentials_file: Path,
    token_response: dict[str, Any],
    pending_payload: dict[str, Any],
) -> None:
    access_token = required_str(token_response, "access_token")
    required_str(token_response, "refresh_token")
    account_id = extract_chatgpt_account_id(access_token)
    if account_id is None:
        raise AuthError("failed to extract account_id from access token")

    payload = dict(token_response)
    payload.update(
        {
            "auth_mode": "chatgpt",
            "account_id": account_id,
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "created_at": int(time.time()),
            "source": "skiller-openai-auth",
            "state_hash": hashlib.sha256(
                required_str(pending_payload, "state").encode("utf-8")
            ).hexdigest(),
        }
    )
    expires_in = optional_int(token_response, "expires_in")
    if expires_in is not None:
        payload["expires_at"] = int(time.time()) + expires_in
    write_json(credentials_file, payload)


def post_codex_stream(
    *,
    access_token: str,
    account_id: str,
    payload: dict[str, Any],
) -> str:
    request = build_json_request(
        CODEX_RESPONSES_URL,
        payload,
        headers={
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {access_token}",
            "OpenAI-Beta": "responses=experimental",
            "User-Agent": CODEX_USER_AGENT,
            "chatgpt-account-id": account_id,
            "originator": "pi",
        },
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
                if event_payload.get("type") in {
                    "response.done",
                    "response.completed",
                    "response.incomplete",
                }:
                    break
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise AuthError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise AuthError(f"request failed: {exc.reason}") from exc
    return "".join(text_parts)


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

    return parse_required_json_object(raw_body)


def parse_required_json_object(raw_body: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise AuthError("response must be JSON") from exc
    if not isinstance(payload, dict):
        raise AuthError("response must contain a JSON object")
    return payload


def parse_json_object(raw_payload: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def extract_chatgpt_account_id(access_token: str) -> str | None:
    parts = access_token.split(".")
    if len(parts) != 3:
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


def write_text_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
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


def first_param(params: dict[str, list[str]], key: str) -> str | None:
    values = params.get(key)
    if not values:
        return None
    return values[0]


def code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def token_urlsafe(length: int) -> str:
    token = secrets.token_urlsafe(length)
    return token[:128]


def oauth_success_html(message: str) -> str:
    return f"<!doctype html><html><body><h1>{escape_html(message)}</h1></body></html>"


def oauth_error_html(message: str) -> str:
    return f"<!doctype html><html><body><h1>{escape_html(message)}</h1></body></html>"


def escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def read_server_log(log_file: Path) -> str:
    if not log_file.exists():
        return "callback server failed"
    text = log_file.read_text(encoding="utf-8", errors="replace").strip()
    return text or "callback server failed"


def cleanup_authorization_files(credentials_file: Path) -> None:
    pending_file(credentials_file).unlink(missing_ok=True)
    callback_file(credentials_file).unlink(missing_ok=True)
    server_file(credentials_file).unlink(missing_ok=True)
    server_ready_file(credentials_file).unlink(missing_ok=True)
    server_log_file(credentials_file).unlink(missing_ok=True)


def default_credentials_file() -> Path:
    explicit_path = os.environ.get("SKILLER_OPENAI_CODEX_CREDENTIALS_FILE", "").strip()
    if explicit_path:
        return Path(explicit_path).expanduser()

    configured_path = configured_credentials_file()
    if configured_path is not None:
        return configured_path

    return Path.home() / ".skiller" / "secrets" / "openai-codex.json"


def configured_credentials_file() -> Path | None:
    config_path = Path(
        os.environ.get(
            "AGENT_AGENT_CONFIG_FILE",
            Path.home() / ".skiller" / "settings" / "agent.json",
        )
    ).expanduser()
    if not config_path.exists():
        return None

    try:
        config = read_json(config_path)
    except AuthError:
        return None

    providers = config.get("providers")
    if not isinstance(providers, dict):
        return None

    codex = providers.get("codex")
    if not isinstance(codex, dict):
        return None

    credentials_file = codex.get("credentials_file")
    if not isinstance(credentials_file, str) or not credentials_file.strip():
        return None

    return Path(credentials_file).expanduser()


def pending_file(credentials_file: Path) -> Path:
    return credentials_file.with_name("openai-codex.pending.json")


def callback_file(credentials_file: Path) -> Path:
    return credentials_file.with_name("openai-codex.callback.json")


def server_file(credentials_file: Path) -> Path:
    return credentials_file.with_name("openai-codex.server.json")


def server_ready_file(credentials_file: Path) -> Path:
    return credentials_file.with_name("openai-codex.callback-ready")


def server_log_file(credentials_file: Path) -> Path:
    return credentials_file.with_name("openai-codex.callback.log")


if __name__ == "__main__":
    raise SystemExit(main())
