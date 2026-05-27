# D. Shell Interrupt

Purpose: verify that ESC or `skiller agent interrupt <run_id>` interrupts a
running shell tool process.

Prompt:

```text
Use the shell tool to run a long command so I can test ESC/interruption.

Run this command as a single shell tool call:

`sleep 10 && echo "should-not-print"`

While it is running, I will press ESC or run `skiller agent interrupt <run_id>`.

After the interruption, report whether Skiller interrupted the tool execution and copy the exact interruption message shown by the tool/runtime.

If the tool is still running and no interruption is observed, ask me to press ESC
or run `skiller agent interrupt <run_id>` again.

`sleep 10 && echo "should-not-print"`

```

Expected behavior:

- The shell process starts.
- ESC or `skiller agent interrupt <run_id>` interrupts the running process.
- The command should not print `should-not-print`.
- Agent context receives the interruption feedback.
- The agent step finishes with `stop_reason = "interrupted"`.
