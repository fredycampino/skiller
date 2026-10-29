# Observe a webhook agent in STUI

Send a message with `curl` and watch the agent respond in STUI. This local demo requires a configured LLM provider. Run the commands from the repository root.

## Create an agent that listens for webhooks

The loop waits at a webhook step, passes the received message to the agent, and returns to listening after each response.

### Agent flow

`agent-wh.yaml`:

```yaml
name: agent-wh
description: "An agent that receives tasks through a webhook"
version: "0.1"
start: wait_task

steps:
  - wait_webhook: wait_task
    webhook: agent-wh
    key: inbox
    next: respond

  - agent: respond
    config:
      file: "./agent-wh.agent.json"
    system:
      file: "./system.md"
    task: '{{output_value("wait_task").payload.message}}'
    tools: []
    next: wait_task
```

### System prompt

`system.md`:

```markdown
You are a helpful assistant receiving tasks through a webhook.
Respond to the task in the language of the message. Keep answers brief and practical.
You have no tools and cannot perform external actions.
```

### Agent profile

`agent-wh.agent.json` inherits the configured provider and model. No tools are exposed to the agent.

```json
{
  "tools": {
    "shell": {
      "allowed_commands": [],
      "allowed_paths": [],
      "allowlist_enabled": true
    },
    "files": {
      "read": [],
      "write": [],
      "all": []
    }
  }
}
```

## Register the webhook

```bash
skiller webhook register agent-wh --auth token --token-header X-Webhook-Token
```

Keep the returned secret private. In the terminal you will use for `curl`, set `WEBHOOK_SECRET` to that secret and `WEBHOOK_URL` to the returned webhook URL, replacing `{key}` with `inbox`. Do not include the secret in the agent's prompt or files.

## Configure the Skiller server

This demo runs locally. For an external service such as Telegram to deliver events to a remote deployment, provide an internet-reachable HTTPS endpoint, typically through a reverse proxy, with webhook authentication enabled. Do not expose an unauthenticated endpoint.

Start the local server and check its status:

```bash
skiller server start
skiller server status
```

Stop it when it is no longer needed:

```bash
skiller server stop
```

Keep it running for the following steps. Telegram integration would also need to adapt its update payload and send the agent's answer back through the Telegram API; neither is included in this demo.

## Open the agent in STUI

Launch `skiller`, then enter:

```text
/run ./packages/skiller/tests/e2e-guides/agent-wh/agent-wh.yaml
```

Keep this run open to observe the agent. It waits for a message on webhook `agent-wh`, key `inbox`. Use a single active demo run so each message reaches only this agent.

## Send a message from another terminal

```bash
curl --fail-with-body -X POST "$WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -H "X-Webhook-Token: $WEBHOOK_SECRET" \
  --data '{"message":"Hello! What can you help me with?"}'
```

Watch STUI: the agent receives the message, generates a response, and returns to waiting. Repeat the request with another message to continue. Each message calls the configured model.

The HTTP response acknowledges delivery; the agent's answer appears in STUI, not in the `curl` response.

## Cleanup

Delete the demo run when finished. Remove the registration if you created it; stop the server only if no other flows need it.

```bash
skiller delete <run_id>
skiller webhook remove agent-wh
skiller server stop
```

## Run the E2E check

```bash
bash packages/skiller/tests/e2e-guides/agent-wh/agent-wh.sh
```

Uses your configured provider and makes one real model call. Runs a separate local server and temporary database, sends the task with `curl`, and verifies the response and return to webhook waiting through CLI logs and status. No STUI is opened. Test resources are cleaned up automatically.

Optional overrides: `SKILLER_RUNTIME_PYTHON`, `SKILLER_TEST_WEBHOOK_PORT` (default `18300`), and `SKILLER_TEST_AGENT_TIMEOUT` (default `120` seconds).
