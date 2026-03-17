#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys


def run_git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--expected-base", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--head-prefix", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.base_ref != args.expected_base:
        fail(
            f"pull request base branch must be {args.expected_base}, got {args.base_ref}"
        )

    if not args.head_ref.startswith(args.head_prefix):
        fail(
            f"pull request head branch must start with {args.head_prefix}, got {args.head_ref}"
        )

    base_remote_ref = f"origin/{args.expected_base}"
    base_sha = run_git("rev-parse", base_remote_ref)
    merge_base_sha = run_git("merge-base", "HEAD", base_remote_ref)
    commit_count = int(run_git("rev-list", "--count", f"{base_remote_ref}..HEAD"))

    if merge_base_sha != base_sha:
        fail(
            f"branch must be rebased directly on top of {base_remote_ref} before opening the PR"
        )

    if commit_count != 1:
        fail(
            "branch must compare as exactly one commit on top of "
            f"{base_remote_ref}, got {commit_count}"
        )

    print(
        "validated PR branch shape: "
        f"{args.head_ref} is one commit directly on top of {base_remote_ref}"
    )


if __name__ == "__main__":
    main()
