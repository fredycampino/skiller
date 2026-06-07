# Codex Auth Credentials

This document describes how Skiller obtains OpenAI Codex credentials through
the `auths/codex` callback flow.

## Goal

`auths/codex` links a ChatGPT/OpenAI account with Skiller and saves Codex OAuth
credentials in:

```text
~/.skiller/secrets/openai-codex.json
```

The flow uses a local OAuth callback endpoint:

```text
http://localhost:1455/auth/callback
```

It does not use the device-code flow.

## Run From TUI

```text
/run auths/codex
```

The TUI shows an OpenAI authorization action. The user opens the link and
authorizes in the browser. The browser returns to the local callback endpoint,
then the flow exchanges the authorization code for tokens, saves the
credentials, writes the Codex provider config, and validates the credentials.

## Flow

```text
check_codex_credentials
prepare_authorization
start_callback_server
open_authorization_url
wait_authorization_callback
exchange_authorization_code
write_codex_config
require_credentials
verify_credentials
credentials_ready
```

## OAuth Callback Data

Pending authorization data is stored in:

```text
~/.skiller/secrets/openai-codex.pending.json
```

The pending file contains short-lived authorization state:

```text
state
code_verifier
redirect_uri
authorization_url
credentials_file
created_at
```

The callback stores temporary callback/server files next to the credentials:

```text
~/.skiller/secrets/openai-codex.callback.json
~/.skiller/secrets/openai-codex.server.json
~/.skiller/secrets/openai-codex.callback-ready
~/.skiller/secrets/openai-codex.callback.log
```

These files are cleanup artifacts and must not be required by the runtime LLM.

## Final Credentials

Final credentials are stored in:

```text
~/.skiller/secrets/openai-codex.json
```

The runtime LLM needs the OAuth token fields used to call and refresh Codex:

```text
access_token
refresh_token
expires_at
expires_in
client_id
id_token
redirect_uri
scope
token_type
auth_mode
created_at
source
```

The auth flow also writes metadata such as:

```text
account_id
state_hash
```

`state_hash` belongs to the auth flow. The runtime LLM must not require it to
call Codex or refresh tokens.

## Sensitive Values

Sensitive values must not be printed to stdout:

```text
authorization_code
code_verifier
access_token
refresh_token
id_token
```

The callback `state` is short-lived auth state and should also stay out of the
transcript. The saved credentials file is written with `0600` permissions.

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
  "model": "gpt-5.5",
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
rm -f ~/.skiller/secrets/openai-codex.callback.json
rm -f ~/.skiller/secrets/openai-codex.server.json
rm -f ~/.skiller/secrets/openai-codex.callback-ready
rm -f ~/.skiller/secrets/openai-codex.callback.log
```

Then run the callback auth flow again:

```text
/run auths/codex
```

If OpenAI returns `token_revoked`, the saved credentials are no longer valid and
must be regenerated.
