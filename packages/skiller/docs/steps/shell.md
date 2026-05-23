# `shell`

## Goal

`shell` executes a command through the host shell and stores the process result as structured output.

## Shape

```yaml
- shell: run_tests
  command: ./.venv/bin/pytest packages/skiller/tests/unit -q
  cwd: .
  env:
    FOO: bar
  timeout: 60
  check: true
  next: done
```

`command` may also be multiline:

```yaml
- shell: prepare
  command: |
    set -e
    mkdir -p /tmp/demo
    echo "hello" > /tmp/demo/out.txt
    cat /tmp/demo/out.txt
```

## Persistence

```json
{
  "output": {
    "text": "hello",
    "value": {
      "ok": true,
      "exit_code": 0,
      "stdout": "hello\n",
      "stderr": ""
    },
    "body_ref": null
  }
}
```

## Rules

- `command` is required.
- runtime resolves the interpreter in this order: `$SHELL`, `/bin/bash`, `/bin/sh`.
- `cwd` is optional and controls the working directory of the process.
- `env` is optional and adds environment variables for the command.
- `timeout` is optional and uses seconds.
- `check` defaults to `true`.
- if `check: true`, a non-zero exit code fails the step.
- if `check: false`, a non-zero exit code still produces `STEP_SUCCESS` with `output.value.ok = false`.

## Runtime Config

The `shell` step does not load configuration from `.json`.

Its `ShellToolRuntimeConfig` is injected by the runtime container with the default policy:

- `workspace = ""`
- `allowlist_enabled = false`
- `allow_env_prefix = true`
- `allowed_commands = ()`

The step YAML only controls the execution request fields documented above: `command`, `cwd`, `env`, `timeout`, `check`, and `next`.

Template access:

```text
{{output_value("run_tests").stdout}}
{{output_value("run_tests").exit_code}}
```

Use `output_value(...)` instead of reading `step_executions.<step_id>.output.value...` directly.
