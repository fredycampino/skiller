from __future__ import annotations


def format_run_name(run_name: str) -> str:
    if "/" not in run_name:
        return run_name
    return f"/{run_name.rsplit('/', maxsplit=1)[-1]}"
