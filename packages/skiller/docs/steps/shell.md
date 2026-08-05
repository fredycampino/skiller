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

## Runtime Shell Config

The `shell` step does not load configuration from `.json`.

Its `ShellToolRuntimeConfig` is injected by the runtime container with the default policy:

- `allowed_paths` contains the resolved current working directory of the
  Skiller process, the current flow directory, and the resolved Python
  executable by default.
- `allowlist_enabled = false`
- `allow_env_prefix = true`
- `allowed_commands = ()`

The step YAML controls the execution request fields documented above: `command`,
`cwd`, `env`, `timeout`, `check`, and `next`, plus the step policy field
`allowed_paths`.
`allowlist_enabled = false` means that commands are not restricted by
`allowed_commands`; path validation remains active. The requested `cwd` and
explicit path arguments in `command` must stay inside one of the configured
`allowed_paths`. A step can explicitly add additional roots:

```yaml
- shell: prepare
  allowed_paths:
    - "{{runtime.venv}}"
    - "~/.skiller"
  command: python "{{flow.dir}}/prepare.py"
```

`allowed_paths` must be a list of non-empty strings. Templates are rendered
before the policy is evaluated, `~` is expanded, and relative paths are
resolved from the Skiller process working directory.
Relative `cwd` values are resolved from the Skiller process working directory.
Relative paths in `command` are resolved from the effective `cwd`, not from the
flow file directory. Use `{{flow.dir}}` for helper files shipped next to the
current flow.

Template access:

```text
{{output_value("run_tests").stdout}}
{{output_value("run_tests").exit_code}}
{{flow.dir}}
{{flow.run_id}}
{{runtime.python}}
{{runtime.venv}}
```

Use `output_value(...)` instead of reading `step_executions.<step_id>.output.value...` directly.
