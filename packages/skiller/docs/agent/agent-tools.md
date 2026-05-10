# Agent Tools

This page documents the tool boundary used by the `agent` loop.

## Current Scope

Supported tools in the current slice:

- `shell`
- `notify`

## Boundary

`agent` does not execute tools directly. `AgentRunner` delegates to `ToolExecutionPort`.
The currently wired implementation is `AgentToolExecution`.

- `ToolExecutionPort`: owns the agent tool-turn execution boundary
- `AgentToolExecution`: persists agent context entries, emits agent tool events, handles
  interrupts, and calls `ToolManager`
- `ToolManager`: validates allowlist, builds `ToolInput`, prepares typed tool requests,
  applies policy, and executes native tools
- `ToolInput`: wraps raw LLM args and exposes typed helpers for tool authors
- `ProcessTool`: converts typed requests to process requests and process output to
  normalized `ToolResult`
- `ToolProcessPort`: starts and waits for tool processes through `popen()` and
  `wait(ToolProcessWait)`
- `SteeringPort`: stores and consumes interrupt/message steering items

## Constraints

`ToolManager` must not:

- update run state
- write `StepExecution`
- persist agent context entries directly
- start processes
- know process internals

Concrete tools must not know:

- YAML step shape
- `CurrentStep`
- `StepExecution`
- `next`
- transcript persistence policy
- agent context persistence policy
- runtime event emission policy
- steering queue persistence

Process tools must not execute or wait for their own process. They only define:

- `request()`: `ToolInput` to typed tool request
- `policy()`: optional validation/normalization before execution
- `call()`: typed tool request to `ToolProcessRequest`
- `result()`: `ToolProcessOutput` to `ToolResult`

`AgentToolExecution` owns the process lifecycle by calling `ToolProcessPort`.

## Adding A Tool

Use this flow when adding a new agent tool.

### 1. Create The Request

Define the typed input for the tool.

```python
from dataclasses import dataclass

from skiller.domain.tool.tool_contract import ToolRequest


@dataclass(frozen=True)
class FilesToolRequest(ToolRequest):
    path: str
```

### 2. Create The Config

The config is what the LLM sees when the tool is enabled.

```python
from skiller.domain.tool.tool_contract import ToolConfig


class FilesToolConfig(ToolConfig):
    def __init__(self) -> None:
        super().__init__(
            name="files",
            description="Read project files",
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
        )
```

### 3. Create The Tool

If the tool is pure Python, implement `Tool`.

```python
from skiller.domain.tool.tool_contract import Tool, ToolInput, ToolResult, ToolResultStatus


class FilesTool(Tool[FilesToolRequest]):
    name = "files"
    config = FilesToolConfig()

    def request(self, input: ToolInput) -> FilesToolRequest:
        return FilesToolRequest(path=input.require_string("path"))

    def run(self, request: FilesToolRequest) -> ToolResult:
        text = read_file_text(request.path)
        return ToolResult(
            name=self.name,
            status=ToolResultStatus.COMPLETED,
            data={"path": request.path, "text": text},
            text=text,
            error=None,
        )
```

If the tool runs an external command, implement `ProcessTool`.

```python
from skiller.domain.tool.tool_contract import (
    ProcessTool,
    ToolInput,
    ToolPolicyResult,
    ToolResult,
    ToolResultStatus,
)
from skiller.domain.tool.tool_process_model import ToolProcessOutput, ToolProcessRequest


class FilesProcessTool(ProcessTool[FilesToolRequest]):
    name = "files"
    config = FilesToolConfig()

    def request(self, input: ToolInput) -> FilesToolRequest:
        return FilesToolRequest(path=input.require_string("path"))

    def policy(self, request: FilesToolRequest) -> ToolPolicyResult[FilesToolRequest]:
        if not is_path_allowed(request.path):
            return ToolPolicyResult.blocked("files path is not allowed")
        return ToolPolicyResult.allowed(request)

    def call(self, request: FilesToolRequest) -> ToolProcessRequest:
        return ToolProcessRequest(
            command=["skiller-files-read", request.path],
        )

    def result(self, output: ToolProcessOutput) -> ToolResult:
        return ToolResult(
            name=self.name,
            status=ToolResultStatus.COMPLETED,
            data={
                "exit_code": output.exit_code,
                "stdout": output.stdout,
                "stderr": output.stderr,
            },
            text=output.stdout.strip() or output.stderr.strip(),
            error=None,
        )
```

The process tool does not call `subprocess`, does not poll, does not wait, and
does not terminate processes.

### 4. Register It

Register the tool in DI.

```python
ToolManager(
    tools=[
        ShellProcessTool(...),
        FilesTool(),
        NotifyTool(),
    ],
)
```

### 5. Add Tests

Minimum useful coverage:

- tool builds the typed request from `ToolInput`
- tool rejects invalid args through `ToolInput`
- policy allows or blocks expected requests
- tool builds the expected `ToolProcessRequest`
- tool converts `ToolProcessOutput` to `ToolResult`
- `ToolManager.prepare()` accepts the tool when it is allowed
- `AgentToolExecution` persists `tool_call` and `tool_result` for a successful tool call

### 6. Enable It

Enable the tool in the agent step config.

```json
{
  "tools": ["files"]
}
```

Summary:

```text
Request -> Config -> Tool -> Policy -> DI -> Tests -> Agent config
```

Execution flow:

```text
AgentRunner
  -> ToolExecutionPort.execute()
  -> AgentToolExecution
  -> ToolManager.prepare()
  -> ToolInput(args)
  -> Tool.request(input)
  -> optional Tool.policy(request)
  -> if native Tool:
       ToolManager.execute_prepared()
       Tool.run()
  -> if ProcessTool:
       ProcessTool.call()
       ToolProcessPort.popen()
       ToolProcessPort.wait(ToolProcessWait)
       ProcessTool.result()
  -> append tool_result
  -> emit AGENT_TOOL_RESULT
```

Interrupt flow for process tools:

```text
skiller agent interrupt <run_id>
  -> SteeringPort.append(SteeringAgentInterrupt)
  -> ToolProcessPort.wait(..., interrupt=ToolProcessInterrupt(...))
  -> AgentToolExecution.is_interrupted(run_id)
  -> SteeringPort.pop(run_id, SteeringAgentInterrupt)
  -> terminate current process
  -> return ToolExecutionStatus.INTERRUPTED
```

## Shell Policy Spec

`shell` policy configuration lives under runtime config (not in YAML `steps/agent`):

```json
{
  "shell": {
    "policy": {
      "allowlist": {
        "enabled": true,
        "workspace": ".",
        "allow_env_prefix": true,
        "allowed_commands": ["ls", "cat", "rg", "git", "pytest"]
      },
      "sandbox": {
        "enabled": false
      }
    }
  }
}
```

### Rules

- `policy.allowlist.enabled` is boolean (`true` / `false`).
- `policy.allowlist.workspace` is a single workspace root path.
- `policy.allowlist.allowed_commands` is the executable allowlist.
- `policy.allowlist.allow_env_prefix` allows env prefixes like `FOO=1 BAR=2 cmd ...`.
- `policy.sandbox.enabled` is reserved for future sandbox execution.

When `allowlist.enabled` is `true`:

- each command segment (`&&`, `||`, `;`, `|`) must resolve to an executable present in
  `allowed_commands`
- if any segment is not allowed, the full command is rejected

When `allowlist.enabled` is `false`:

- allowlist executable filtering is skipped

Always enforced (independent from allowlist toggle):

- `ToolInput` argument validation (`command`, `cwd`, `env`, `timeout`)
- command-critical security blocking
- workspace path boundaries for `cwd` and command path candidates

### Future Sandbox

`policy.sandbox.enabled` is intentionally defined next to `allowlist` so sandboxing can be enabled
later without changing the external configuration shape.

## Related Docs

- [`../steps/agent.md`](../steps/agent.md)
- [`./agent-context.md`](./agent-context.md)
- [`./agent-event.md`](./agent-event.md)
