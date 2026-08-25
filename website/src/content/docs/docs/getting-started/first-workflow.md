---
title: Your first workflow
description: Understand the minimum YAML shape and run it from a file.
---

A workflow has a name, a starting step, and an ordered set of named steps:

```yaml
name: hello
start: greet

steps:
  - notify: greet
    message: "Hello from skiller.run!"
```

Save it as `hello.yaml`, then run:

```bash
skiller run --file ./hello.yaml
```

The Runtime validates the definition, creates a persisted run, executes `greet`, and returns the observed status as JSON.

## Step shape

Each step starts with one primary header:

```yaml
- <step_type>: <step_id>
```

The primary key selects behavior and the value gives that execution point a unique name. A `next` field connects a step to the following step; omitting it ends the successful flow.

## Next

Use the complete [Hello workflow](/docs/demos/hello-workflow/) to pass inputs and inspect the resulting run.
