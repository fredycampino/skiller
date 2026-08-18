#!/usr/bin/env python3
"""CLI entrypoint for the sanitized Codex stream probe."""

from __future__ import annotations

try:
    from scripts.qa.codex.codex_stream_probe import main
except ModuleNotFoundError:
    from codex.codex_stream_probe import main

if __name__ == "__main__":
    raise SystemExit(main())
