---
title: Installation
description: Install skiller and verify the CLI.
---

skiller requires Python 3.11 or newer. For regular CLI usage, install it in an isolated environment with `pipx`:

```bash
pipx install skiller
```

Verify the installation:

```bash
skiller --version
skiller --help
```

## Development checkout

When working from the repository, use the project virtual environment:

```bash
uv sync
./.venv/bin/skiller --help
```

Commands in the demos use `skiller`. Replace it with `./.venv/bin/skiller` when you are running directly from a checkout without an activated environment.

## Next

Run the [Hello workflow](/docs/demos/hello-workflow/). It requires no provider credentials or external services.
