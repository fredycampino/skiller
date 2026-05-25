# OpenAI Auth Local Callback

This document describes how Skiller obtains OpenAI Codex credentials through
the `openai-auth` agent.

## Goal

`openai-auth` links a ChatGPT/OpenAI account with Skiller using the same local
callback endpoint used by Pi:

```text
http://localhost:1455/auth/callback
```

Credentials are saved in:

```text
~/.skiller/secrets/openai-auth.json
```

This flow is intended for local desktop use, where the browser can reach the
same `localhost` as the Skiller process.

## Run From TUI

```text
/run openai-auth
```

The TUI opens the OpenAI authorization URL. After the browser login completes,
OpenAI redirects to:

```text
http://localhost:1455/auth/callback?code=...&state=...
```

The local callback server receives the authorization code, writes it to the
pending credentials file, and the run continues.

The user does not need to copy or type a device code.

## Flow

```text
prepare_authorization
start_callback_server
open_authorization_url
wait_authorization_callback
exchange_authorization_code
require_credentials
verify_credentials
credentials_ready
```

## OAuth Authorization

The authorization URL is built from:

```text
GET https://auth.openai.com/oauth/authorize
```

Parameters:

```text
response_type=code
client_id=app_EMoamEEZ73f0CkXaXp7hrann
redirect_uri=http://localhost:1455/auth/callback
scope=openid profile email offline_access
code_challenge=<pkce challenge>
code_challenge_method=S256
state=<random state>
id_token_add_organizations=true
codex_cli_simplified_flow=true
originator=pi
```

The callback server validates:

```text
path == /auth/callback
state == pending.state
code is present
```

The authorization code is not printed to stdout and is not passed through
`wait_input` or `wait_webhook`.

## Token Exchange

After the callback arrives, the agent exchanges the code:

```text
POST https://auth.openai.com/oauth/token
```

Form payload:

```text
grant_type=authorization_code
client_id=app_EMoamEEZ73f0CkXaXp7hrann
code=<authorization_code>
code_verifier=<pkce verifier>
redirect_uri=http://localhost:1455/auth/callback
```

The token response must contain:

```text
access_token
refresh_token
expires_in
```

The agent extracts `chatgpt_account_id` from the access token and stores it as
`account_id`.

## Sensitive Files

Pending authorization state is stored in:

```text
~/.skiller/secrets/openai-auth.pending.json
```

The local callback result is stored in:

```text
~/.skiller/secrets/openai-auth.callback.json
```

Final credentials are stored in:

```text
~/.skiller/secrets/openai-auth.json
```

Runtime server metadata may be written to:

```text
~/.skiller/secrets/openai-auth.server.json
~/.skiller/secrets/openai-auth.callback-ready
~/.skiller/secrets/openai-auth.callback.log
```

Sensitive values that must not be printed to stdout:

```text
state
code_verifier
authorization_code
access_token
refresh_token
```

The final credentials and pending files are written with `0600` permissions.

## Credential Validation

Validation uses the Codex Responses backend:

```text
POST https://chatgpt.com/backend-api/codex/responses
```

Required behavior:

```text
stream=true
instructions present
SSE response parsing
```

Current validation payload:

```json
{
  "model": "gpt-5.2",
  "store": false,
  "stream": true,
  "instructions": "You are a credential validation probe. Reply only with the requested marker.",
  "input": [
    {
      "role": "user",
      "content": "Reply with exactly: skiller-openai-codex-ok"
    }
  ],
  "text": {
    "verbosity": "low"
  },
  "include": ["reasoning.encrypted_content"],
  "tool_choice": "auto",
  "parallel_tool_calls": true
}
```

Headers:

```text
Authorization: Bearer <access_token>
chatgpt-account-id: <account_id>
originator: pi
OpenAI-Beta: responses=experimental
Accept: text/event-stream
Content-Type: application/json
User-Agent: pi (skiller)
```

The verifier reads SSE `response.output_text.delta` events and expects:

```text
skiller-openai-codex-ok
```

## UX And Limitations

This is the best UX when Skiller and the browser run on the same local machine:

```text
no device code
no manual paste
automatic callback
no authorization code in run DB
```

It is not ideal for remote SSH, containers, or WSL setups where the browser
cannot reach the Skiller process at `localhost:1455`.

For those environments, use the device-code agent instead:

```text
/run codex-auth
```

## Cleanup

Remove local credentials and pending state:

```bash
rm -f ~/.skiller/secrets/openai-auth.json
rm -f ~/.skiller/secrets/openai-auth.pending.json
rm -f ~/.skiller/secrets/openai-auth.callback.json
rm -f ~/.skiller/secrets/openai-auth.server.json
rm -f ~/.skiller/secrets/openai-auth.callback-ready
rm -f ~/.skiller/secrets/openai-auth.callback.log
```

Then run again:

```text
/run openai-auth
```
