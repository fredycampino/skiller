from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

PACKAGE_NAME = "skiller"
UNKNOWN_VERSION = "unknown"


def resolve_app_version() -> str:
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return UNKNOWN_VERSION


def format_app_version() -> str:
    return f"v{resolve_app_version()}"
