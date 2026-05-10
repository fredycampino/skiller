from __future__ import annotations

import pytest
from stui.screen.prompt import PromptTextArea, compact_pasted_prompt_text

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


def test_prompt_text_area_decodes_multiline_paste_reference() -> None:
    prompt = PromptTextArea()
    prompt.text = "[paste #1 +2 lines]"
    prompt._multiline_paste_payloads = {  # noqa: SLF001
        "[paste #1 +2 lines]": "linea asdasdasd\nsegunda linea\ntercera linea"
    }

    assert prompt.decoded_text() == "linea asdasdasd\nsegunda linea\ntercera linea"


def test_prompt_text_area_clears_paste_memory_when_text_is_deleted() -> None:
    prompt = PromptTextArea()
    prompt.text = ""
    prompt._multiline_paste_payloads = {  # noqa: SLF001
        "[paste #1 +2 lines]": "linea asdasdasd\nsegunda linea\ntercera linea"
    }

    prompt.sync_paste_memory()

    assert prompt._multiline_paste_payloads == {}  # noqa: SLF001
