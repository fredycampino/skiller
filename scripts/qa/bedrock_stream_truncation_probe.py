"""CLI entrypoint for the Bedrock streaming truncation probe."""

from __future__ import annotations

try:
    from bedrock.bedrock_stream_truncation_probe import main
except ModuleNotFoundError:
    from scripts.qa.bedrock.bedrock_stream_truncation_probe import main

if __name__ == "__main__":
    raise SystemExit(main())
