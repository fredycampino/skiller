from __future__ import annotations

import pytest

from stui.screen.prompt import PromptTextArea, compact_pasted_prompt_text

pytestmark = pytest.mark.unit


def test_compact_pasted_prompt_text_keeps_single_line_text() -> None:
    assert compact_pasted_prompt_text("hola mundo", paste_count=1) == "hola mundo"


def test_compact_pasted_prompt_text_removes_trailing_newline_from_single_line() -> None:
    assert (
        compact_pasted_prompt_text(
            "/run openai-auth\n",
            paste_count=1,
        )
        == "/run openai-auth"
    )


def test_compact_pasted_prompt_text_compacts_long_single_line() -> None:
    assert compact_pasted_prompt_text("x" * 161, paste_count=2) == "[paste #2 +0 lines]"


def test_compact_pasted_prompt_text_compacts_multiline_text_to_reference() -> None:
    assert (
        compact_pasted_prompt_text(
            "linea asdasdasd\nsegunda linea\ntercera linea",
            paste_count=1,
        )
        == "[paste #1 +2 lines]"
    )


def test_prompt_text_area_decodes_multiline_paste_reference() -> None:
    prompt = PromptTextArea()
    prompt.text = "[paste #1 +2 lines]"
    prompt._multiline_paste_payloads = {  # noqa: SLF001
        "[paste #1 +2 lines]": "linea asdasdasd\nsegunda linea\ntercera linea"
    }

    assert prompt.decoded_text() == "linea asdasdasd\nsegunda linea\ntercera linea"
