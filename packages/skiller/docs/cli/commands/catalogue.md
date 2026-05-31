# CLI Command Catalogue

This catalogue defines the intended public status of each `skiller` CLI surface.

Status values:
- `stable`: user-facing command intended for normal use.
- `dev`: development/operator command that should live under `skiller dev ...`.
- `experimental`: available surface with behavior still being validated.

| Command | Description | Status |
| --- | --- | --- |
| `skiller --help` | Show root CLI help. | stable |
| `skiller --version` | Show installed package version. | stable |
| `skiller run` | Start a run from the internal catalogue or an external YAML file. | stable |
| `skiller resume` | Resume a waiting run. | stable |
| `skiller status` | Read one run status. | stable |
| `skiller runs` | List recent runs. | stable |
| `skiller logs` | Read raw runtime events for a run. | stable |
| `skiller action` | Update persisted runtime action state. | stable |
| `skiller input` | Human input operations. | stable |
| `skiller webhook` | Webhook ingress and registration operations. | stable |
| `skiller agent` | Agent control and context diagnostics. | stable |
| `skiller server` | Local webhook server process operations. | stable |
| `skiller channel` | Channel ingress operations. | experimental |
| `skiller delete` | Delete a run and associated rows. | dev |
| `skiller worker` | Local worker process operations. | dev |
| `skiller cloudflared` | Local cloudflared tunnel operations. | dev |
| `skiller whatsapp` | Local WhatsApp bridge and pairing operations. | dev |
