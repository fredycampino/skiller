# Agent Tool Development

This document explains how to add and verify a simple agent tool using the
current runtime contracts.

Useful built-in references:

- `FilesTool`: direct in-process tool with policy and runtime config
- `ShellProcessTool`: process tool with policy and runtime config

## Runtime Flow

The agent receives tool calls from the LLM and executes them through this path:

```text
LLM tool call
-> AgentToolExecutor
-> ToolManager.prepare()
-> tool.request(ToolInput)
-> optional tool.policy(config, request)
-> ToolManager.execute_prepared() for direct tools
-> or ProcessTool.call() + ToolProcessPort + ProcessTool.result() for process tools
-> ToolResult
```

`ToolManager.prepare()` is the boundary that turns raw LLM args into a typed request and applies policy.

## Mandatory Contract

Every agent tool is a `ToolDefinition`.

```python
class ToolDefinition(ABC, Generic[RequestT]):
    name: ClassVar[str]
    description: ClassVar[str]

    def schema(self) -> ToolSchema: ...

    def request(self, input: ToolInput) -> ToolRequestResult[RequestT]: ...
```

Responsibilities:

- `name`: stable tool name used by YAML, LLM tool calls, runtime config, and result validation.
- `description`: public description sent to the LLM.
- `schema()`: JSON-schema-like parameter schema sent to the LLM.
- `request()`: maps raw `ToolInput.args` into a typed `ToolRequest`.

The tool name must be unique in the runtime container.

## Typed Request

Each tool should define a typed request model.

```python
@dataclass(frozen=True)
class MyToolRequest(ToolRequest):
    value: str
```

Use `ToolInput` helpers in `request()`:

- `require_string(name)`
- `optional_string(name)`
- `optional_number(name)`
- `optional_string_map(name)`

Return invalid input as `ToolRequestResult.invalid(...)`. Do not raise for normal bad LLM input.

```python
def request(self, input: ToolInput) -> ToolRequestResult[MyToolRequest]:
    try:
        return ToolRequestResult.valid(
            MyToolRequest(
                value=input.require_string("value"),
            )
        )
    except ValueError as exc:
        return ToolRequestResult.invalid(str(exc))
```

## Direct Tool

Use `Tool[RequestT]` when the tool can run in-process.

```python
class MyTool(ToolDefinition[MyToolRequest], Tool[MyToolRequest]):
    name: ClassVar[str] = "my_tool"
    description: ClassVar[str] = "Do one clear thing"

    def schema(self) -> ToolSchema:
        return ToolSchema(
            value={
                "type": "object",
                "properties": {
                    "value": {"type": "string"},
                },
                "required": ["value"],
                "additionalProperties": False,
            }
        )

    def request(self, input: ToolInput) -> ToolRequestResult[MyToolRequest]:
        try:
            return ToolRequestResult.valid(
                MyToolRequest(
                    value=input.require_string("value"),
                )
            )
        except ValueError as exc:
            return ToolRequestResult.invalid(str(exc))

    def run(
        self,
        *,
        config: ToolRuntimeConfig | None,
        request: MyToolRequest,
    ) -> ToolResult:
        return ToolResult(
            name=self.name,
            status=ToolResultStatus.COMPLETED,
            data={"value": request.value},
            text=request.value,
            error=None,
        )
```

`ToolManager.execute_prepared()` validates that the returned `ToolResult.name` matches the prepared tool name.

## Process Tool

Use `ProcessTool[RequestT]` when the tool must run through the managed process runner.

```python
class MyProcessTool(
    ToolDefinition[MyToolRequest],
    ProcessTool[MyToolRequest],
):
    name: ClassVar[str] = "my_process_tool"
    description: ClassVar[str] = "Run an external process"

    def schema(self) -> ToolSchema: ...

    def request(self, input: ToolInput) -> ToolRequestResult[MyToolRequest]: ...

    def call(
        self,
        *,
        config: ToolRuntimeConfig | None,
        request: MyToolRequest,
    ) -> ToolProcessRequest:
        return ToolProcessRequest(
            command=["my-command", request.value],
            cwd=None,
            env={},
            timeout=None,
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
            text=output.stdout.strip() or None,
            error=None,
        )
```

Process tools are executed by `AgentToolExecutor` through `ToolProcessPort`. This is the path used by `shell`.

## Optional Policy

Implement `ToolPolicy[RequestT]` when the tool needs runtime validation after typed request mapping.

```python
class MyTool(
    ToolDefinition[MyToolRequest],
    Tool[MyToolRequest],
    ToolPolicy[MyToolRequest],
):
    def policy(
        self,
        *,
        config: ToolRuntimeConfig | None,
        request: MyToolRequest,
    ) -> ToolPolicyResult[MyToolRequest]:
        if request.value == "blocked":
            return ToolPolicyResult.blocked("value is blocked")
        return ToolPolicyResult.allowed(request)
```

Policy runs after `request()` and before execution.

Policy blocked is agent-correctable: the result is persisted as tool feedback instead of crashing the runtime.

Policy exceptions are runtime failures for the agent step.

## Optional Runtime Config

Implement `ConfiguredTool[ConfigT]` only when the tool needs config from `agent.json`.

```python
@dataclass(frozen=True)
class MyToolRuntimeConfig(ToolRuntimeConfig):
    limit: int = 10
```

The runtime config must carry the tool definition type through `ToolRuntimeConfig.definition`.

```python
class MyTool(
    ToolDefinition[MyToolRequest],
    Tool[MyToolRequest],
    ConfiguredTool[MyToolRuntimeConfig],
):
    def to_runtime_config(
        self,
        raw: Mapping[str, object],
    ) -> MyToolRuntimeConfig:
        return MyToolRuntimeConfig(
            definition=type(self),
            limit=10,
        )
```

Rules:

- If a tool implements `ConfiguredTool`, `ToolManager.prepare()` requires a runtime config.
- If a tool does not implement `ConfiguredTool`, it does not read runtime config from `agent.json`.
- Runtime config is loaded by `AgentConfigMapper` using the tools registered in the container.
- Runtime config is selected at execution time by tool name.

Current configurable tools: `shell`, `files`.

For `files`, `agent.json` accepts these path allowlists:

```json
{
  "tools": {
    "files": {
      "read": ["/path/to/read"],
      "write": ["/path/to/write"],
      "all": ["/path/to/read-and-write"]
    }
  }
}
```

`files` uses policy to reject reads, writes, and edits outside the configured
directories. Relative file requests are resolved from the current process
working directory before that policy check.

## Register The Tool

Add the tool instance to the agent tool tuple in the runtime container.

```python
my_tool = MyTool()
agent_tools = (
    shell_tool,
    files_tool,
    my_tool,
)
```

That tuple is used by:

- `AgentConfigMapper`, to validate/load tool runtime config from `agent.json`
- `ToolManager`, to resolve tool names and execute tool calls
- `AgentStepConfigReader`, to turn YAML tool names into `ToolDefinition` objects for the LLM request

## Enable The Tool In YAML

An agent step enables tools by name:

```yaml
- agent: support_agent
  system: You can use tools when useful.
  task: Inspect the repository.
  tools:
    - my_tool
```

If the tool name is not registered in the container, step config reading fails.

## Add Runtime Config In `agent.json`

Only configurable tools can use this.

```json
{
  "tools": {
    "my_tool": {
      "limit": 10
    }
  }
}
```

Do not add `agent.json` config for non-configurable tools; they will not read it.

## Expected Tests

Minimum useful tests:

- `request()` maps valid args into the typed request.
- `request()` returns invalid for bad LLM args.
- `policy()` allows and blocks expected cases, if implemented.
- `to_runtime_config()` accepts valid config and rejects invalid config, if implemented.
- direct tool `run()` returns a valid `ToolResult`, if implemented.
- process tool `call()` builds the expected `ToolProcessRequest`, if implemented.
- process tool `result()` maps `ToolProcessOutput` into `ToolResult`, if implemented.
- `ToolManager.prepare()` integration for the tool when behavior depends on manager semantics.

Avoid tests that only restate dataclass defaults or duplicate another layer's behavior.

## Checklist

- The tool extends `ToolDefinition`.
- `name` is unique and stable.
- `schema()` matches what `request()` accepts.
- `request()` returns `ToolRequestResult.invalid(...)` for normal bad input.
- `run()` or `call()`/`result()` returns `ToolResult` with matching `name`.
- Policy is only added when it protects real runtime behavior.
- Runtime config is only added when the tool actually needs external config.
- The tool is registered in the runtime container.
- The tool is enabled by name in the agent step YAML.
