# CLI Command Catalogue

This catalogue defines the intended public status of each `skiller` CLI surface.

Status values:
- `stable`: documented in `commands/` and intended as public CLI surface.
- `experimental`: available surface with behavior still being validated.
- `dev`: development/operator command for debugging or controlled execution.

| Command | Description | Status | Contract |
| --- | --- | --- | --- |
| `skiller --help` | Show root CLI help. | stable | n/a |
| `skiller --version` | Show installed package version. | stable | n/a |
| `skiller run` | Start a run from the internal catalogue or an external YAML file. | stable | [`commands/run.md`](commands/run.md) |
| `skiller resume` | Resume a waiting run. | stable | [`commands/resume.md`](commands/resume.md) |
| `skiller status` | Read one run status. | stable | [`commands/status.md`](commands/status.md) |
| `skiller runs` | List recent runs. | stable | [`commands/runs.md`](commands/runs.md) |
| `skiller logs` | Read raw runtime events for a run. | stable | [`commands/logs.md`](commands/logs.md) |
| `skiller action` | Update persisted runtime action state. | stable | [`commands/action.md`](commands/action.md) |
| `skiller input` | Human input operations. | stable | [`commands/input.md`](commands/input.md) |
| `skiller webhook` | Webhook ingress and registration operations. | stable | [`commands/webhook.md`](commands/webhook.md) |
| `skiller agent` | Agent control and context diagnostics. | stable | [`commands/agent.md`](commands/agent.md) |
| `skiller server` | Local webhook server process operations. | stable | [`commands/server.md`](commands/server.md) |
| `skiller delete` | Delete a run and associated rows. | stable | [`commands/delete.md`](commands/delete.md) |
| `skiller channel` | Channel ingress operations. | experimental | [`commands/channel-exp.md`](commands/channel-exp.md) |
| `skiller worker` | Local worker process operations. | dev | [`commands/worker-dev.md`](commands/worker-dev.md) |
