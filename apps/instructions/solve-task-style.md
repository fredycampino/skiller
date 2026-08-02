## Solve Task Workflow

Use this workflow when the user asks to solve a problem, fix a bug, implement a feature, perform a refactor, or handle an unclear task. Do not apply it to simple questions that only require an explanation or a factual answer.

### Be Sure You Understand The Problem

When the user reports a story, bug, feature request, refactor, or unclear task, do not start modifying files immediately.

- Understand and restate the problem.
- If the problem is not clear, ask for confirmation.

### Planning Before Changes

Propose a concise action plan that follows the architecture and code style of the affected package.

Do not implement or solve Runtime and TUI changes in the same pass.

Split cross-layer problems into Runtime and TUI phases. Inspect both layers when needed, but edit one responsibility at a time.

Allowed before approval:

- Reading files.
- Running non-destructive inspection commands.
- Checking git status, diffs, logs, and relevant tests when useful.

### Present The Plan Solution

- Describe the solution at a high level first.
- Keep solutions concrete and clear.
- Avoid verbose explanations.
- If the user needs details, they will ask.
- Mark acceptance criteria clearly.
- Wait for user approval before applying code changes.

### Execute After Approval

When the user approves the plan or explicitly asks to implement, continue until the acceptance criteria are met.

Do not ask for permission at every implementation step. Use the approved plan to make the required edits, run focused verification, fix issues introduced by the change, and report the final result.

Stop and ask only when:

- the implementation would cross from Runtime to TUI or from TUI to Runtime
- the approved plan no longer fits the discovered code
- there are unrelated user changes that would be affected
- there is a merge/rebase/conflict or destructive action not covered by the plan
- verification fails for a reason that requires a product or architecture decision

### Present Results

- Pass tests before reporting completion.
- Check the architecture rules.
- Describe results at a high level first.
- Do not create commits during normal delivery.
- The user reviews the working tree and explicitly decides whether to commit.
- You may suggest a commit, but must not run git commit without explicit approval.
- Do not amend, squash, reset, rebase, or rewrite commits unless explicitly requested or required by an approved PR/release procedure.

### Exceptions To This Flow

- Explicitly requested defined procedures, such as preparing, updating, completing, or opening a PR/release, may run end-to-end according to the Procedure Autonomy section.
- Tiny documentation/config wording changes requested directly by the user may be applied if the requested edit is unambiguous.
- Tiny edits may be applied directly only when the requested change is explicit, local, and does not cross architecture boundaries.
