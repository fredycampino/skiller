## Tool permissions

Tool permissions are configured in `agent.json`. Never bypass permission checks.

### Shell

- `tools.shell.allowed_commands`: executable names allowed when `allowlist_enabled` is `true`.
- `tools.shell.allowed_paths`: additional roots allowed for `cwd` and command paths.
- `{{runtime.cwd}}` and `{{runtime.python}}` are always allowed.
- Supported path templates: `{{flow.dir}}`, `{{runtime.cwd}}`, `{{runtime.python}}`, `{{runtime.venv}}`.

### Files

- `tools.files.read`: read access.
- `tools.files.write`: write and edit access.
- `tools.files.all`: read, write, and edit access.
- No paths are allowed by default.
- Supported path templates: `{{flow.dir}}`, `{{runtime.cwd}}`, `{{runtime.venv}}`.

Paths may also be absolute, use `~`, or be relative to the `agent.json` that defines `tools`. Other templates are invalid.

### Missing permissions

If no permitted alternative exists, ask the user to update `agent.json` with the required command or path. State the exact field and value needed.
