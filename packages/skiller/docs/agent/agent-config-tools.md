# Agent Tool Configuration Internals

User-facing configuration is maintained in the website:

- [Harness tools](https://skiller.run/docs/tools/overview/): enabling tools, configuration inheritance, and security limitations.
- [Shell](https://skiller.run/docs/tools/shell/): fields, templates, command checks, and defaults.
- [Files](https://skiller.run/docs/tools/files/): read/write policies, templates, and defaults.

## Configuration mapping

`AgentConfigMapper` delegates configurable tool payloads to their registered
runtime configuration mappers. `ShellToolRuntimeConfigMapper` and
`FilesToolRuntimeConfigMapper` produce immutable runtime configuration objects.
They validate supported keys and value types before execution.

`resolve_tool_path_template` substitutes the explicitly supplied template map
and rejects unresolved template delimiters. Each tool mapper defines its own
supported map. Paths are expanded and resolved using the current flow directory
as the configuration base.

The shell mapper adds the resolved Runtime Python executable to its roots and
deduplicates them. It does not add an executable-name allowlist entry. The files
mapper adds no implicit roots.

## Shell policy implementation

`ShellCommandPolicy` resolves the effective working directory, parses outer
command segments, and checks executable basenames and detected path candidates.
`ShellCommandExpander` handles validation-time expansion and removes literal
heredoc bodies before command inspection.

Command-name validation and path validation are independent. Neither evaluates
operations inside scripts, nested interpreters, or external executables. These
checks are operational guardrails, not a sandbox or an isolation boundary.

## Files policy implementation

`FilesToolPolicy` combines shared grants with the action-specific roots, resolves
the requested path, and returns either a blocked policy result or an updated
request containing its effective path. Read selects read roots; write and edit
select write roots. Root checks use resolved paths, including symlink targets.

## Documentation boundary

Keep mapper responsibilities, parsing behavior, and policy implementation here.
Maintain configuration examples, fields, defaults, and user-facing limitations
in the linked website references.
