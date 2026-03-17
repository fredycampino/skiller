#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path

PLACEHOLDER_LINES = {
    "- Nothing yet.",
    "- Update this section when a branch is ready for release.",
}
ALLOWED_FILES = {"CHANGELOG.md", "pyproject.toml"}


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
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--expected-base", required=True)
    return parser.parse_args()


def extract_release_version(head_ref: str) -> str:
    prefix = "release/"
    if not head_ref.startswith(prefix):
        fail(f"release PR head branch must start with {prefix}, got {head_ref}")
    version = head_ref[len(prefix) :].strip()
    if not version:
        fail("release branch must include a version suffix, for example release/1.2.3")
    return version


def validate_changed_files(base_ref: str) -> None:
    changed_files = {
        path
        for path in run_git("diff", "--name-only", f"origin/{base_ref}..HEAD").splitlines()
        if path
    }
    if changed_files != ALLOWED_FILES:
        fail(
            "release PR must change only CHANGELOG.md and pyproject.toml, "
            f"got: {sorted(changed_files)}"
        )


def validate_pyproject_version(expected_version: str) -> None:
    with Path("pyproject.toml").open("rb") as file_handle:
        pyproject = tomllib.load(file_handle)

    project_version = pyproject["project"]["version"]
    if project_version != expected_version:
        fail(
            "pyproject.toml version must match release branch version "
            f"{expected_version}, got {project_version}"
        )


def validate_changelog(expected_version: str) -> None:
    lines = Path("CHANGELOG.md").read_text(encoding="utf-8").splitlines()

    try:
        unreleased_start = lines.index("## Unreleased") + 1
    except ValueError as error:
        raise SystemExit("CHANGELOG.md is missing the Unreleased section") from error

    unreleased_end = len(lines)
    for index in range(unreleased_start, len(lines)):
        if lines[index].startswith("## "):
            unreleased_end = index
            break

    unreleased_entries = {
        line.strip()
        for line in lines[unreleased_start:unreleased_end]
        if line.strip().startswith("- ")
    }
    meaningful_unreleased_entries = unreleased_entries - PLACEHOLDER_LINES
    if meaningful_unreleased_entries:
        fail(
            "CHANGELOG.md Unreleased must be reset before opening a release PR, "
            f"got entries: {sorted(meaningful_unreleased_entries)}"
        )

    version_prefix = f"## {expected_version} - "
    version_line_index = next(
        (index for index, line in enumerate(lines) if line.startswith(version_prefix)),
        None,
    )
    if version_line_index is None:
        fail(
            f"CHANGELOG.md must contain a closed section for version {expected_version}"
        )

    version_end = len(lines)
    for index in range(version_line_index + 1, len(lines)):
        if lines[index].startswith("## "):
            version_end = index
            break

    version_entries = [
        line.strip()
        for line in lines[version_line_index + 1 : version_end]
        if line.strip().startswith("- ")
    ]
    meaningful_version_entries = [
        line for line in version_entries if line not in PLACEHOLDER_LINES
    ]
    if not meaningful_version_entries:
        fail(
            f"CHANGELOG.md version section {expected_version} must contain release notes"
        )


def main() -> None:
    args = parse_args()

    if args.base_ref != args.expected_base:
        fail(
            f"release PR base branch must be {args.expected_base}, got {args.base_ref}"
        )

    expected_version = extract_release_version(args.head_ref)
    validate_changed_files(args.expected_base)
    validate_pyproject_version(expected_version)
    validate_changelog(expected_version)

    print(f"validated release PR metadata for version {expected_version}")


if __name__ == "__main__":
    main()
