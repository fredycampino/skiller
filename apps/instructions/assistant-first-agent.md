# Assisted First Agent Creation

## Purpose And Interaction

Guide new Skiller users through creating their first agent, one step at a time.
Show the result of each step and invite the user to continue. Keep the tutorial
conversation in Flows; use CLI commands for demonstrations instead of switching
the active STUI run.

## Tutorial Procedure

### 1. Choose A Name

Ask for a short lowercase name if needed, with examples such as `helper`, `coco`,
or `reviewer`. Establish its purpose without introducing advanced configuration.

### 2. Create A Minimal Agent

Determine the actual current working directory. Propose this layout:

```text
<working-directory>/<name>/<name>.yaml
<working-directory>/<name>/system.md
~/.skiller/profiles/agent.<name>.json
```

#### Flow Template

```yaml
name: <name>
description: "My first custom agent"
version: "0.1"
start: ask_user

steps:
  - wait_input: ask_user
    prompt: "Write a task."
    next: <name>

  - agent: <name>
    config:
      file: "~/.skiller/profiles/agent.<name>.json"
    system:
      file: "./system.md"
    task: '{{output_value("ask_user").payload.text}}'
    tools:
      - shell
    next: ask_user
```

Each task executes one cycle, then the agent waits for the next task. Responses
already appear in the transcript; no additional notification is needed.

#### System Template

```markdown
You are <name>, a helpful assistant.
Help the user with the agreed purpose of this agent.
Reply in the language of the user and keep answers clear and concise.
Ask for clarification when essential information is missing.
Do not claim to have performed actions that you have not performed.
```

Replace the generic purpose sentence with the actual agreed purpose. Keep the
initial prompt short; refine it with the user later.

#### Profile Template

```json
{
  "tools": {
    "shell": {
      "allowed_paths": ["{{runtime.cwd}}"],
      "allowed_commands": ["pwd", "ls", "find", "cat", "head", "tail", "wc", "rg"],
      "allowlist_enabled": true
    },
    "files": {
      "read": [],
      "write": [],
      "all": []
    }
  }
}
```

The profile inherits the provider and model from `~/.skiller/settings/agent.json`
and overrides its tools section. Shell access is limited to `{{runtime.cwd}}`;
the files tool is not enabled.

#### Register And Check

Add the absolute directory containing `<name>/` to the effective `flow_paths`,
preserving existing settings. See `<path-docs>/config/config.md`.

Validate the flow and referenced files. With user approval, run
`skiller run @<name>` and confirm `WAITING`. This startup check does not call the
model or verify an agent turn. Keep the returned `run_id` for the demo.

Show the YAML, system prompt, and profile, then invite the user to try the agent.

### 3. Explain Runs

Explain that the files define the agent and each run is a separate instance.
Show both launch commands:

- CLI: `skiller run @<name>`.
- STUI: `/run @<name>`.

Continue the CLI demo using the run already created, keeping Flows active in STUI.

### 4. Send A First Task

Propose a short task suited to the agent purpose. Explain that in STUI the user
would type the task while the new agent run is active. For this tutorial use CLI:

```bash
skiller input receive <run_id> --text "<agreed-task>" --wait
```

Agree on the task before sending it; this step calls the model. Target the demo
run, not the Flows run. Check the response and return to `WAITING` with
`skiller status <run_id>` and `skiller logs <run_id>` as needed.

### 5. Explain The Profile

Show `~/.skiller/profiles/agent.<name>.json` and explain how `config.file` selects
it. Contrast profile overrides with the global `~/.skiller/settings/agent.json`:
root sections replace global sections rather than merging recursively.

### 6. Explain Shell Permissions

Explain `tools` in YAML, `allowed_commands`, and `allowed_paths` using the
existing profile. Offer to run `pwd` and `ls` in the Runtime working directory.
Clarify that shell permissions are not an operating-system sandbox.

### 7. Explain File Permissions

Explain `read`, `write` (write and edit), and `all` (both). These grants apply to
the files tool, not shell commands.

Offer a read-only exercise with a harmless local file. If accepted, add `files`
to the YAML tools and grant the required read path in the profile. Relative
permission paths resolve from the flow directory, not the profile directory.

### 8. Refine The System Prompt

Show `<name>/system.md` and explain that it defines the purpose, behavior, and
limits of the agent. Agree on one small improvement, edit it, and offer a test.

### 9. Add Reusable Instructions

Explain that `system.md` defines the agent identity while `instructions` adds
reusable guidance. Read `<path-docs>/steps/agent.md` for reference resolution.
Offer to create `<name>/instructions/response-style.md` with a short agreed rule,
then reference it on the agent step:

```yaml
instructions:
  - "./instructions/response-style.md"
```

Check the reference and offer a test. Prompt loading does not require files-tool
permissions. See `<path-docs>/steps/agent.md` for instruction resolution.

Close with the created file locations, the launch command, and an optional next
improvement.
