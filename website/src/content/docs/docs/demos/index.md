---
title: Demos
description: Small executable workflows that introduce skiller.run one capability at a time.
---

Start with a deterministic workflow, then add persisted input, agents, branching, and external events.

| Demo | What it shows | Requires an LLM |
| --- | --- | --- |
| [Hello workflow](./hello-workflow/) | Inputs, `assign`, and `notify` | No |
| [Interactive flow](./interactive-flow/) | `wait_input` and durable resume | No |
| [Agent chat](./agent-chat/) | An LLM-backed `agent` step | Yes |
| [Branching workflow](./branching-workflow/) | Input-based routing with `switch` | No |
| [Webhook workflow](./webhook-workflow/) | Waiting for an external event | No |

All source files live in the repository [`examples/`](https://github.com/fredycampino/skiller/tree/main/examples) directory.
