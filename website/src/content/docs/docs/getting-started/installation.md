---
title: Installation
description: Install Skiller with pipx or in a virtual environment.
prev: false
---

Requires Python 3.11+.

## Install with pipx

Install Skiller in an isolated environment with [pipx](https://pipx.pypa.io/stable/installation/).

```bash
pipx install skiller
```

## Install in a .venv

Create and activate a virtual environment, then install Skiller.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install skiller
```

On Windows, create the environment with `py -m venv .venv` and activate it with `.venv\Scripts\activate` (Command Prompt) or `.venv\Scripts\Activate.ps1` (PowerShell).

## Verify installation

```bash
skiller --version
```
