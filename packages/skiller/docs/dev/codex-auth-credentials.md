# Codex Auth Credentials

This document describes how Skiller obtains OpenAI Codex credentials through
the `codex-auth` agent.

## Goal

`codex-auth` links a ChatGPT/OpenAI account with Skiller and saves Codex OAuth
credentials in:

```text
~/.skiller/secrets/openai-codex.json
```

The flow follows the same device-code approach used by Hermes Agent for
`openai-codex`. It does not use a localhost callback and does not use Skiller
webhooks.

## Run From TUI

```text
/run codex-auth
```

The TUI shows an OpenAI authorization action. The user opens the link and enters
the displayed user code.

After the browser authorization is completed, the agent polls OpenAI, exchanges
the authorization code for tokens, saves the credentials, and validates them.

## Flow

```text
request_device_authorization
load_user_code
open_device_authorization
poll_device_auth
exchange_device_authorization
require_credentials
verify_credentials
credentials_ready
```

## OpenAI Device Auth Endpoints

Request a device authorization:

```text
POST https://auth.openai.com/api/accounts/deviceauth/usercode
```

Payload:

```json
{
  "client_id": "app_EMoamEEZ73f0CkXaXp7hrann"
}
```

The response contains:

```text
device_auth_id
user_code
interval
expires_at
```

The user authorizes in:

```text
https://auth.openai.com/codex/device
```

Poll until authorized:

```text
POST https://auth.openai.com/api/accounts/deviceauth/token
```

Payload:

```json
{
  "device_auth_id": "...",
  "user_code": "..."
}
```

While the user has not authorized yet, OpenAI may return `403` or `404`. The
agent treats those statuses as pending and keeps polling.

When authorized, OpenAI returns:

```text
authorization_code
code_verifier
```

Exchange for credentials:

```text
POST https://auth.openai.com/oauth/token
```

Form payload:

```text
grant_type=authorization_code
code=<authorization_code>
redirect_uri=https://auth.openai.com/deviceauth/callback
client_id=app_EMoamEEZ73f0CkXaXp7hrann
code_verifier=<code_verifier>
```

## Sensitive Files

Pending authorization data is stored in:

```text
~/.skiller/secrets/openai-codex.pending.json
```

Final credentials are stored in:

```text
~/.skiller/secrets/openai-codex.json
```

Both files are written with `0600` permissions.

Sensitive values that must not be printed to stdout:

```text
device_auth_id
authorization_code
code_verifier
access_token
refresh_token
```

The `user_code` is shown to the user and appears in the run transcript. It is
short-lived and does not grant access by itself, but it should still be treated
as auth-related data.

## HTTP Headers

The auth endpoints reject or misroute Python's default `urllib` user agent in
some environments. Skiller sends an explicit user agent for auth requests:

```text
User-Agent: skiller-codex-auth/0.1
Accept: application/json
```

For Codex Responses validation, Skiller uses Codex-style headers:

```text
User-Agent: codex_cli_rs/0.0.0 (Skiller)
originator: codex_cli_rs
ChatGPT-Account-ID: <extracted from access token when available>
```

## Credential Validation

Validation uses:

```text
POST https://chatgpt.com/backend-api/codex/responses
```

This endpoint is not Chat Completions and is not regular non-streaming
Responses. It requires streaming.

Required request shape:

```json
{
  "model": "gpt-5.2",
  "instructions": "You are a credential validation probe. Reply only with the requested marker.",
  "input": [
    {
      "role": "user",
      "content": "Reply with exactly: skiller-openai-codex-ok"
    }
  ],
  "store": false,
  "stream": true
}
```

The response is SSE. The verifier reads `response.output_text.delta` events and
expects:

```text
skiller-openai-codex-ok
```

Observed failures:

```text
HTTP 400 {"detail":"Instructions are required"}
HTTP 400 {"detail":"Stream must be set to true"}
HTTP 401 token_revoked
```

## Revocation And Cleanup

If credentials are compromised or revoked, remove local files:

```bash
rm -f ~/.skiller/secrets/openai-codex.json
rm -f ~/.skiller/secrets/openai-codex.pending.json
```

Then run the agent again:

```text
/run codex-auth
```

If OpenAI returns `token_revoked`, the saved credentials are no longer valid and
must be regenerated.
