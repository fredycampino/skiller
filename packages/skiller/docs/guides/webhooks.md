# Register a webhook

A run can pause at `wait_webhook` and resume when an external application sends a matching webhook event. While it waits, no worker process stays alive: Skiller persists the run state and starts a worker again only when the event arrives. This is the minimum flow:

```yaml
name: webhook-example
description: Receive a webhook event
version: "0.1"
start: wait_event

steps:
  - wait_webhook: wait_event
    webhook: provider-events
    key: inbox
    next: show_event

  - notify: show_event
    message: '{{output_value("wait_event").payload.message}}'
```

Run the commands from the Skiller environment that runs the flow.

## Register the webhook

```bash
skiller webhook register provider-events \
  --auth token \
  --token-header X-Webhook-Token
```

The command returns the webhook details:

```json
{
  "webhook": "provider-events",
  "status": "REGISTERED",
  "method": "POST",
  "auth": "token",
  "payload_source": "body_json",
  "token_header": "X-Webhook-Token",
  "secret": "<secret>",
  "enabled": true,
  "webhook_url": "http://127.0.0.1:8001/webhooks/provider-events/{key}"
}
```

Copy the returned `secret`.

## Start the Skiller server

```bash
skiller server start
skiller server status
```

Make sure the status reports `"running": true`:

```json
{
  "running": true,
  "managed_by_skiller": true,
  "endpoint": "http://127.0.0.1:8001/health",
  "pid": 12345
}
```

## Webhook endpoint

The external application must send a `POST` request to this endpoint. The request
must include the following header:

```text
https://<public-host>/webhooks/provider-events/inbox
```

```text
X-Webhook-Token: <secret>
```

## Run the flow

From Skiller STUI, start the flow.

From the terminal:

```bash
skiller run --file ./webhook-example.yaml
```

## Trigger the webhook locally

```bash
curl -X POST \
  'http://127.0.0.1:8001/webhooks/provider-events/inbox' \
  -H 'Content-Type: application/json' \
  -H 'X-Webhook-Token: <secret>' \
  --data '{"message":"Hello from a webhook"}'
```

## Expected result

The flow resumes and `wait_event` receives:

```json
{
  "message": "Hello from a webhook"
}
```

## Verify

```bash
skiller webhook list
skiller server status
```

## Remove the webhook

```bash
skiller webhook remove provider-events
```
