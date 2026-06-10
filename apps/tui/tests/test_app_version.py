from __future__ import annotations

from importlib.metadata import PackageNotFoundError

import pytest

from stui import app_version

pytestmark = pytest.mark.unit


def test_format_app_version_uses_installed_package_version(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_version(package_name: str) -> str:
        assert package_name == "skiller"
        return "0.1.0-beta.8"

    monkeypatch.setattr(app_version, "version", fake_version)

    assert app_version.format_app_version() == "v0.1.0-beta.8"


def test_format_app_version_falls_back_when_package_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_version(package_name: str) -> str:
        assert package_name == "skiller"
        raise PackageNotFoundError(package_name)

    monkeypatch.setattr(app_version, "version", fake_version)

    assert app_version.format_app_version() == "vunknown"
