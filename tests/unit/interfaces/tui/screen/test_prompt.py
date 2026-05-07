from __future__ import annotations

import pytest

from skiller.interfaces.tui.screen.prompt import compact_pasted_prompt_text

pytestmark = pytest.mark.unit


def test_compact_pasted_prompt_text_keeps_single_line_text() -> None:
    assert compact_pasted_prompt_text("hola mundo", paste_count=1) == "hola mundo"


def test_compact_pasted_prompt_text_compacts_multiline_text_to_reference() -> None:
    assert (
        compact_pasted_prompt_text(
            "linea asdasdasd\nsegunda linea\ntercera linea",
            paste_count=1,
        )
        == "[paste #1 +2 lines]"
    )


def test_compact_pasted_prompt_text_counts_blank_lines() -> None:
    assert (
        compact_pasted_prompt_text(
            "\n\n  primera linea  \n\nsegunda",
            paste_count=3,
        )
        == "[paste #3 +4 lines]"
    )


def test_compact_pasted_prompt_text_uses_singular_for_one_extra_line() -> None:
    assert compact_pasted_prompt_text("uno\ndos", paste_count=7) == "[paste #7 +1 line]"
