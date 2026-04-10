# Runtime Events

This document defines the runtime event contract used by `/logs`, `watch`, the CLI, and the UI transcript.

## Event Model

Every runtime event follows this shape:

```json
{
  "id": "f2d2f7ef-5d58-4e2a-a7dd-48a4bb0d3f18",
  "type": "EVENT_NAME",
  "run_id": "e367bf20-7457-4c44-a4be-e48796025e1c0",
  "created_at": "2026-03-28T10:30:15Z",
  "payload": {}
}
```

Rules:
- `id` uniquely identifies the event.
- `type` identifies the event contract.
- `run_id` identifies the run instance.
- `created_at` records when the event was created.
- `payload` contains the event-specific data.

## Output Envelope

When an event exposes step output, it always uses:

```json
{
  "text": "...",
  "text_ref": "data.reply",
  "value": {},
  "body_ref": null
}
```

Rules:
- `text` is always present.
- `text_ref` is optional and points to the field inside the full body value that can rebuild the full human text.
- `value` is always an object or `null`.
- `body_ref` is always present and may be `null`.
- if `body_ref` is not `null`, `output.value` is the small observable summary
- backend `/logs`, `watch`, and `status` keep this small payload.
- the UI may resolve `body_ref` separately for display.
- templates do not read `body_ref` directly; they use `output_value("<step_id>")`, which resolves the canonical `output.value` lazily when needed.

## Generic Events

### `RUN_CREATE`

```json
{
  "type": "RUN_CREATE",
  "payload": {
    "skill": "chat"
  }
}
```

### `RUN_RESUME`

```json
{
  "type": "RUN_RESUME",
  "payload": {
    "source": "manual"
  }
}
```

### `STEP_STARTED`

```json
{
  "type": "STEP_STARTED",
  "payload": {
    "step": "answer",
    "step_type": "llm_prompt"
  }
}
```

### `STEP_SUCCESS`

```json
{
  "type": "STEP_SUCCESS",
  "payload": {
    "step": "answer",
    "step_type": "llm_prompt",
    "output": {
      "text": "hello back",
      "value": {
        "data": {
          "reply": "hello back"
        }
      },
      "body_ref": null
    },
    "next": "ask_user"
  }
}
```

### `STEP_ERROR`

```json
{
  "type": "STEP_ERROR",
  "payload": {
    "step": "answer",
    "step_type": "llm_prompt",
    "error": "LLM step 'answer' returned invalid JSON"
  }
}
```

### `RUN_WAITING`

```json
{
  "type": "RUN_WAITING",
  "payload": {
    "step": "ask_user",
    "step_type": "wait_input",
    "output": {
      "text": "Write a message. Type exit, quit, or bye to stop.",
      "value": {
        "prompt": "Write a message. Type exit, quit, or bye to stop.",
        "payload": null
      },
      "body_ref": null
    }
  }
}
```

Example for `wait_channel`:

```json
{
  "type": "RUN_WAITING",
  "payload": {
    "step": "listen_whatsapp",
    "step_type": "wait_channel",
    "output": {
      "text": "Waiting channel: whatsapp:all.",
      "value": {
        "channel": "whatsapp",
        "key": "all",
        "payload": null
      },
      "body_ref": null
    }
  }
}
```

### `RUN_FINISHED`

Succeeded:

```json
{
  "type": "RUN_FINISHED",
  "payload": {
    "status": "SUCCEEDED"
  }
}
```

Failed:

```json
{
  "type": "RUN_FINISHED",
  "payload": {
    "status": "FAILED",
    "error": "LLM step 'answer' returned invalid JSON"
  }
}
```

## Output By Step Type

### `assign`

```json
{
  "text": "Values assigned.",
  "value": {
    "assigned": {
      "action": "retry"
    }
  },
  "body_ref": null
}
```

### `notify`

```json
{
  "text": "retry chosen",
  "value": {
    "message": "retry chosen"
  },
  "body_ref": null
}
```

### `shell`

```json
{
  "text": "hello",
  "value": {
    "ok": true,
    "exit_code": 0,
    "stdout": "hello\n",
    "stderr": ""
  },
  "body_ref": null
}
```

### `switch`

```json
{
  "text": "Route selected: answer.",
  "value": {
    "next_step_id": "answer"
  },
  "body_ref": null
}
```

### `wait_channel`

```json
{
  "text": "Channel message received: whatsapp:172584771580071@lid.",
  "value": {
    "channel": "whatsapp",
    "key": "172584771580071@lid",
    "payload": {
      "channel": "whatsapp",
      "message_id": "msg-1",
      "key": "172584771580071@lid",
      "sender_id": "172584771580071@lid",
      "sender_name": "Fede",
      "text": "hola",
      "timestamp": 1775388655
    }
  },
  "body_ref": null
}
```

### `when`

```json
{
  "text": "Route selected: good.",
  "value": {
    "next_step_id": "good"
  },
  "body_ref": null
}
```

### `wait_input`

Waiting:

```json
{
  "text": "Write a short summary",
  "value": {
    "prompt": "Write a short summary",
    "payload": null
  },
  "body_ref": null
}
```

Resolved:

```json
{
  "text": "Input received.",
  "value": {
    "prompt": "Write a short summary",
    "payload": {
      "text": "database timeout"
    }
  },
  "body_ref": null
}
```

### `wait_webhook`

Waiting:

```json
{
  "text": "Waiting webhook: github-pr-merged:42.",
  "value": {
    "webhook": "github-pr-merged",
    "key": "42",
    "payload": null
  },
  "body_ref": null
}
```

Resolved:

```json
{
  "text": "Webhook received: github-pr-merged:42.",
  "value": {
    "webhook": "github-pr-merged",
    "key": "42",
    "payload": {
      "merged": true
    }
  },
  "body_ref": null
}
```

### `llm_prompt`

Normal:

```json
{
  "text": "hello back",
  "value": {
    "data": {
      "reply": "hello back"
    }
  },
  "body_ref": null
}
```

With `large_result: true`:

```json
{
  "text": "Europa es uno de los continentes más pequeños...",
  "text_ref": "data.reply",
  "value": {
    "data": {
      "reply": "Europa es uno de los continentes más pequeños...",
      "reply_length": 980,
      "truncated": true
    }
  },
  "body_ref": "execution_output:abc123"
}
```

### `mcp`

```json
{
  "text": "local-mcp.files_action completed successfully.",
  "value": {
    "data": {
      "ok": true,
      "path": "/tmp/demo.txt"
    }
  },
  "body_ref": null
}
```

With `large_result: true`:

```json
{
  "text": "local-mcp.search completed successfully.",
  "value": {
    "data": {
      "ok": true,
      "total": 248,
      "items_count": 248,
      "truncated": true
    }
  },
  "body_ref": "execution_output:abc123"
}
```
