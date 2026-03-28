from __future__ import annotations

import pytest

from skiller.tools.ui.theme import build_prompt_toolkit_style_dict, theme

pytestmark = pytest.mark.unit


def test_build_prompt_toolkit_style_dict_uses_theme_error_color() -> None:
    result = build_prompt_toolkit_style_dict(ui_theme=theme)

    assert result["status.error"] == f"fg:{theme.color_error}"
