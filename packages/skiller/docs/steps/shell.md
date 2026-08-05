# `shell`

## Goal

`shell` executes a command through the host shell and stores the process result as structured output.

## Shape

```yaml
- shell: run_tests
  allowed_paths:
    - "{{runtime.venv}}"
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
    mkdir -p ./demo
    echo "hello" > ./demo/out.txt
    cat ./demo/out.txt
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

## Allowed_paths

`allowed_paths` defines the directories where the command may work. The runtime
validates the process `cwd` and any explicit paths used in `command`.

The `shell` step does not load this configuration from `agent.json`. By
default, the runtime allows:

- the directory where Skiller was launched: `{{runtime.cwd}}`;
- the directory containing the current flow `{{flow.dir}}`;
- the Python executable used by Skiller: `{{runtime.python}}`.

Paths declared in `allowed_paths` are added to these defaults. For example:

```yaml
- shell: prepare
  allowed_paths:
    - "."
    - "{{runtime.venv}}"
    - "~/.skiller"
  command: python "{{flow.dir}}/prepare.py"
```

- `{{runtime.venv}}` represents the active Python virtual environment.
- `~/.skiller` represents the user's `.skiller` directory.
- `"."` and other relative paths are resolved from the directory containing
  the flow YAML file.

## Available templates to commands

```text
{{output_value("run_tests").stdout}}
{{output_value("run_tests").exit_code}}
{{flow.dir}}
{{flow.run_id}}
{{runtime.python}}
{{runtime.venv}}
```

Use `output_value(...)` instead of reading
`step_executions.<step_id>.output.value...` directly.
