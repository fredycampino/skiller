# Compact Context E2E Prompt

Manual E2E for context compaction and LLM request logging.

Run from the repository root.

## Files

- Flow: `packages/skiller/tests/e2e-agent/compact/agent.yaml`
- Agent config: `packages/skiller/tests/e2e-agent/compact/agent.json`
- Helper script: `packages/skiller/tests/e2e-agent/compact/scripts/compact_e2e.py`
- Workspace: `packages/skiller/tests/e2e-agent/compact/workspace`
- Report: `packages/skiller/tests/e2e-agent/compact/reports/compact-context-e2e-results.md`

Runtime files stay under `workspace/`. The final report is written under
`reports/`.

## Expected Context

| sequence | entry | usage_json | prompt_tokens | delta_tokens | delta_compact_tokens | window_start_sequence | window_base | prunable |
|---:|---|---|---:|---:|---:|---:|---|---|
| 1 | user: final `COMPACT-E2E-HOLA` | no | null | null | entry estimate | null | no | no |
| 2 | assistant final | yes | reported | marker delta | entry estimate | 1 | yes | no |
| 3 | user: run shell `echo compact-e2e-tool` | no | null | null | entry estimate | null | no | no |
| 4 | assistant tool_calls | yes | reported | marker delta | null | 1 | no | yes |
| 5 | tool_call: shell `echo compact-e2e-tool` | no | null | null | null | null | no | yes |
| 6 | tool_result: shell stdout | no | null | null | null | null | no | yes |
| 7 | assistant final | yes | reported | marker delta | entry estimate | 1 | no | no |
| 8 | user: run shell `echo compact-e2e-tool` again | no | null | null | entry estimate | null | no | no |
| 9 | assistant tool_calls | yes | reported | marker delta | null | 1 | no | yes |
| 10 | tool_call: shell `echo compact-e2e-tool` | no | null | null | null | null | no | yes |
| 11 | tool_result: shell stdout | no | null | null | null | null | no | yes |
| 12 | assistant final | yes | reported | marker delta | entry estimate | 1 | no | no |
| 13 | user: final from prior shell result | no | null | null | entry estimate | null | no | no |
| 14 | assistant final | yes | reported | marker delta | entry estimate | 1 | yes | no |

Expected request logs: `0001.json` through `0006.json`.

Do not send `exit` before all four user inputs have been processed and the
step validations have been reviewed.

## Start LM Studio

```bash
test -f /home/fede/.skiller/secrets/lmstudio_api_key
lms daemon up
lms server start --port 1234
lms load google/gemma-4-12b-qat --context-length 8000
lms ps
curl -s \
  -H "Authorization: Bearer $(cat /home/fede/.skiller/secrets/lmstudio_api_key)" \
  http://127.0.0.1:1234/v1/models
```

## Prepare

```bash
export PYTHONPATH=packages/skiller/src
export RUNTIME_PYTHON=./.venv/bin/python
export COMPACT_DIR=packages/skiller/tests/e2e-agent/compact
export COMPACT_SCRIPT="$COMPACT_DIR/scripts/compact_e2e.py"
export AGENT_DB_PATH="$PWD/$COMPACT_DIR/workspace/compact-manual-runtime.db"
export AGENT_AGENT_CONFIG_FILE="$PWD/$COMPACT_DIR/agent.json"
export REPORT_PATH="$PWD/$COMPACT_DIR/reports/compact-context-e2e-results.md"
export STATUS_PATH="$PWD/$COMPACT_DIR/reports/compact-context-e2e-status.json"
export REQUEST_LOG_DIR="$(dirname "$AGENT_DB_PATH")/llm-requests/lmstudio"

"$RUNTIME_PYTHON" "$COMPACT_SCRIPT" prepare
rm -f "$REPORT_PATH" "$STATUS_PATH"
```

## Start Run

```bash
RUN_JSON="$(
  "$RUNTIME_PYTHON" -m skiller run \
    --file "$COMPACT_DIR/agent.yaml"
)"

RUN_ID="$(
  RUN_JSON="$RUN_JSON" python3 -c 'import json, os; print(json.loads(os.environ["RUN_JSON"])["run_id"])'
)"

echo "$RUN_ID"
"$RUNTIME_PYTHON" -m skiller status "$RUN_ID"
```

Expected: `WAITING` at `ask_user`.

## Step 1: Final Answer

`input receive` resumes the matched run automatically.

Input:

```bash
"$RUNTIME_PYTHON" -m skiller input receive "$RUN_ID" \
  --text 'Return final answer exactly: COMPACT-E2E-HOLA'
"$RUNTIME_PYTHON" -m skiller status "$RUN_ID"
```

Expected run state: `WAITING`.

### Context Expected

| seq | entry_type | usage_json | delta_tokens | delta_compact_tokens | window_start_sequence | window_base |
|---:|---|---|---|---|---:|---|
| 1 | `user_message` | no | no | yes | null | no |
| 2 | `assistant final` | yes | yes | yes | 1 | yes |

### Context Validation

Read the current snapshot:

```bash
"$RUNTIME_PYTHON" "$COMPACT_SCRIPT" snapshot \
  --db-path "$AGENT_DB_PATH" \
  --log-dir "$REQUEST_LOG_DIR"
```

Validate the `context` section against the `Context Expected` table:

### Request Logs Expected

| field | expected |
|---|---|
| files | `0001.json` |
| request messages | `system`, `user` |
| response | present |
| error | `null` |

### Request Logs Validation

Use the same snapshot output and validate the `requests` section against the
`Request Logs Expected` table.

## Step 2: Shell Echo Tool Call

Input:

```bash
"$RUNTIME_PYTHON" -m skiller input receive "$RUN_ID" \
  --text 'Run shell command echo compact-e2e-tool. After the tool result, return final answer exactly: COMPACT-E2E-ECHO'
"$RUNTIME_PYTHON" -m skiller status "$RUN_ID"
```

Expected run state: `WAITING`.

### Context Expected

| seq | entry_type | usage_json | delta_tokens | delta_compact_tokens | window_start_sequence | window_base |
|---:|---|---|---|---|---:|---|
| 1 | `user_message` | no | no | yes | null | no |
| 2 | `assistant final` | yes | yes | yes | 1 | yes |
| 3 | `user_message` | no | no | yes | null | no |
| 4 | `assistant tool_calls` | yes | yes | no | 1 | no |
| 5 | `tool_call` | no | no | no | null | no |
| 6 | `tool_result` | no | no | no | null | no |
| 7 | `assistant final` | yes | yes | yes | 1 | no |

### Context Validation

Read the current snapshot:

```bash
"$RUNTIME_PYTHON" "$COMPACT_SCRIPT" snapshot \
  --db-path "$AGENT_DB_PATH" \
  --log-dir "$REQUEST_LOG_DIR"
```

Validate the `context` section against the `Context Expected` table.

### Request Logs Expected

Focus only on `0003.json`.

Expected request shape:

| order | role | content |
|---:|---|---|
| 1 | `system` | system prompt |
| 2 | `user` | `COMPACT-E2E-HOLA` input |
| 3 | `assistant final` | `COMPACT-E2E-HOLA` |
| 4 | `user` | asks to run shell `echo compact-e2e-tool` |
| 5 | `assistant tool_calls` | shell `echo compact-e2e-tool` |
| 6 | `tool_result` | stdout `compact-e2e-tool` |

Expected `0003.json` metadata:

| field | expected |
|---|---|
| response | present |
| error | `null` |

### Request Logs Validation

1. Open `0003.json` and validate that `request.messages` contains exactly the
   roles from the request shape table above.

2. Validate token consistency:

   Sum every `delta_tokens` value present in `snapshot.context`.

   The result must be approximately equal to
   `0003.json.response.usage.prompt_tokens`.

   Use `prompt_tokens`, not `total_tokens`.

## Step 3: Second Shell Echo Tool Call

Input:

```bash
"$RUNTIME_PYTHON" -m skiller input receive "$RUN_ID" \
  --text 'Run shell command echo compact-e2e-tool. After the tool result, return final answer exactly: COMPACT-E2E-ECHO-AGAIN'
"$RUNTIME_PYTHON" -m skiller status "$RUN_ID"
```

Expected run state: `WAITING`.

### Context Expected

| seq | entry_type | usage_json | delta_tokens | delta_compact_tokens | window_start_sequence | window_base |
|---:|---|---|---|---|---:|---|
| 1 | `user_message` | no | no | yes | null | no |
| 2 | `assistant final` | yes | yes | yes | 1 | yes |
| 3 | `user_message` | no | no | yes | null | no |
| 4 | `assistant tool_calls` | yes | yes | no | 1 | no |
| 5 | `tool_call` | no | no | no | null | no |
| 6 | `tool_result` | no | no | no | null | no |
| 7 | `assistant final` | yes | yes | yes | 1 | no |
| 8 | `user_message` | no | no | yes | null | no |
| 9 | `assistant tool_calls` | yes | yes | no | 1 | no |
| 10 | `tool_call` | no | no | no | null | no |
| 11 | `tool_result` | no | no | no | null | no |
| 12 | `assistant final` | yes | yes | yes | 1 | no |

### Context Validation

Read the current snapshot:

```bash
"$RUNTIME_PYTHON" "$COMPACT_SCRIPT" snapshot \
  --db-path "$AGENT_DB_PATH" \
  --log-dir "$REQUEST_LOG_DIR"
```

Validate the `context` section against the `Context Expected` table.

### Request Logs Expected

Focus only on `0005.json`.

Expected request shape:

| order | role | content |
|---:|---|---|
| 1 | `system` | system prompt |
| 2 | `user` | `COMPACT-E2E-HOLA` input |
| 3 | `assistant final` | `COMPACT-E2E-HOLA` |
| 4 | `user` | asks to run first shell `echo compact-e2e-tool` |
| 5 | `assistant tool_calls` | shell `echo compact-e2e-tool` |
| 6 | `tool_result` | stdout `compact-e2e-tool` |
| 7 | `assistant final` | `COMPACT-E2E-ECHO` |
| 8 | `user` | asks to run second shell `echo compact-e2e-tool` |
| 9 | `assistant tool_calls` | shell `echo compact-e2e-tool` |
| 10 | `tool_result` | stdout `compact-e2e-tool` |

Expected `0005.json` metadata:

| field | expected |
|---|---|
| response | present |
| response final text | `COMPACT-E2E-ECHO-AGAIN` |
| error | `null` |

### Request Logs Validation

1. Open `0005.json` and validate that `request.messages` contains exactly the
   roles from the request shape table above.

2. Validate that `0005.json.response` is a final assistant message with no tool
   calls and text `COMPACT-E2E-ECHO-AGAIN`.

3. Validate compact token estimate:

   Sum `delta_tokens` for the latest `keep_last` usage markers in
   `snapshot.context` after this step.

   Sum `delta_compact_tokens` for the older compacted entries that appear before
   those protected blocks.

   The total must be approximately equal to
   `0005.json.response.usage.prompt_tokens`.

## Step 4: Final Answer From Prior Context

Input:

```bash
"$RUNTIME_PYTHON" -m skiller input receive "$RUN_ID" \
  --text 'Using the previous shell echo tool result, return final answer exactly: COMPACT-E2E-PREVIOUS-ECHO'
"$RUNTIME_PYTHON" -m skiller status "$RUN_ID"
```

Expected run state: `WAITING`.

### Context Expected

| seq | entry_type | usage_json | delta_tokens | delta_compact_tokens | window_start_sequence | window_base |
|---:|---|---|---|---|---:|---|
| 1 | `user_message` | no | no | yes | null | no |
| 2 | `assistant final` | yes | yes | yes | 1 | yes |
| 3 | `user_message` | no | no | yes | null | no |
| 4 | `assistant tool_calls` | yes | yes | no | 1 | no |
| 5 | `tool_call` | no | no | no | null | no |
| 6 | `tool_result` | no | no | no | null | no |
| 7 | `assistant final` | yes | yes | yes | 1 | no |
| 8 | `user_message` | no | no | yes | null | no |
| 9 | `assistant tool_calls` | yes | yes | no | 1 | no |
| 10 | `tool_call` | no | no | no | null | no |
| 11 | `tool_result` | no | no | no | null | no |
| 12 | `assistant final` | yes | yes | yes | 1 | no |
| 13 | `user_message` | no | no | yes | null | no |
| 14 | `assistant final` | yes | yes | yes | 1 | yes |

### Context Validation

Read the current snapshot:

```bash
"$RUNTIME_PYTHON" "$COMPACT_SCRIPT" snapshot \
  --db-path "$AGENT_DB_PATH" \
  --log-dir "$REQUEST_LOG_DIR"
```

Validate the `context` section against the `Context Expected` table.

### Request Logs Expected

Focus only on `0006.json`.

Expected request shape:

| order | role | content |
|---:|---|---|
| 1 | `system` | system prompt |
| 2 | `user` | `COMPACT-E2E-HOLA` input |
| 3 | `assistant final` | `COMPACT-E2E-HOLA` |
| 4 | `user` | asks to run first shell `echo compact-e2e-tool` |
| 5 | `assistant final` | `COMPACT-E2E-ECHO` |
| 6 | `user` | asks to run second shell `echo compact-e2e-tool` |
| 7 | `assistant tool_calls` | shell `echo compact-e2e-tool` |
| 8 | `tool_result` | stdout `compact-e2e-tool` |
| 9 | `assistant final` | `COMPACT-E2E-ECHO-AGAIN` |
| 10 | `user` | asks final answer from previous shell echo result |

Expected `0006.json` metadata:

| field | expected |
|---|---|
| response | present |
| response final text | `COMPACT-E2E-PREVIOUS-ECHO` |
| error | `null` |

### Request Logs Validation

1. Open `0006.json` and validate that `request.messages` contains exactly the
   roles from the request shape table above.

2. Validate that the first shell tool call/result is absent from `0006.json`,
   and the second shell tool call/result is still present.

3. Validate that `0006.json.response` is a final assistant message with no tool
   calls and text `COMPACT-E2E-PREVIOUS-ECHO`.

4. Validate compact token estimate:

   Sum `delta_tokens` for the latest `keep_last` usage markers in
   `snapshot.context` after this step.

   Sum `delta_compact_tokens` for the older compacted entries that appear before
   those protected blocks.

   The total must be approximately equal to
   `0006.json.response.usage.prompt_tokens`.

## Exit

Only run this after the four step validations have been reviewed.

```bash
"$RUNTIME_PYTHON" -m skiller input receive "$RUN_ID" --text 'exit'
"$RUNTIME_PYTHON" -m skiller status "$RUN_ID" > "$STATUS_PATH"
cat "$STATUS_PATH"
```

Expected final status: `SUCCEEDED`.

## Write Report

```bash
"$RUNTIME_PYTHON" "$COMPACT_SCRIPT" write-report \
  --run-id "$RUN_ID" \
  --db-path "$AGENT_DB_PATH" \
  --log-dir "$REQUEST_LOG_DIR" \
  --status-path "$STATUS_PATH" \
  --report-path "$REPORT_PATH"
```

The report includes:

- summary checks
- every context marker row
- final messages
- request windows as role lists only

## Cleanup

```bash
"$RUNTIME_PYTHON" "$COMPACT_SCRIPT" cleanup \
  --report-path "$REPORT_PATH"

cat "$REPORT_PATH"
```

## Stop LM Studio

```bash
lms unload --all
lms server stop
lms daemon down
```
