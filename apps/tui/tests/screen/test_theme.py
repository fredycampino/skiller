from __future__ import annotations

import pytest

from stui.screen.theme import DEFAULT_TUI_THEME, build_textual_css

pytestmark = pytest.mark.unit


def test_build_textual_css_uses_nord_background_for_surfaces() -> None:
    css = build_textual_css(DEFAULT_TUI_THEME)

    assert DEFAULT_TUI_THEME.color_background == "#282C34"
    assert "ansi_default" not in css
    assert "on default" not in css
    assert "background: #282C34;" in css
    assert "background: #282C34 0%;" in css
    assert "App {\n            background: #282C34;" in css
    assert "Screen {\n            layout: vertical;\n            background: #282C34;" in css
    assert (
        "#root {\n"
        "            layout: vertical;\n"
        "            height: 100%;\n"
        "            background: #282C34;"
    ) in css
