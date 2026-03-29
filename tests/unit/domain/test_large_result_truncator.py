import pytest

from skiller.domain.large_result_truncator import LargeResultTruncator

pytestmark = pytest.mark.unit


def test_truncate_keeps_scalars_and_marks_truncated() -> None:
    truncator = LargeResultTruncator(max_string_chars=20)

    result = truncator.truncate(
        {
            "ok": True,
            "total": 248,
            "error": None,
        }
    )

    assert result == {
        "truncated": True,
        "ok": True,
        "total": 248,
        "error": None,
    }


def test_truncate_summarizes_lists_and_dicts() -> None:
    truncator = LargeResultTruncator(max_string_chars=20)

    result = truncator.truncate(
        {
            "items": [{"id": "a1"}, {"id": "a2"}],
            "meta": {"source": "search", "region": "eu"},
        }
    )

    assert result == {
        "truncated": True,
        "items_count": 2,
        "meta_keys": ["region", "source"],
    }


def test_truncate_keeps_short_strings_inline() -> None:
    truncator = LargeResultTruncator(max_string_chars=20)

    result = truncator.truncate({"message": "short text"})

    assert result == {
        "truncated": True,
        "message": "short text",
    }


def test_truncate_cuts_long_strings_and_keeps_original_length() -> None:
    truncator = LargeResultTruncator(max_string_chars=10)

    result = truncator.truncate({"message": "0123456789abcdef"})

    assert result == {
        "truncated": True,
        "message": "0123456...",
        "message_length": 16,
    }


def test_truncate_top_level_array_to_count_summary() -> None:
    truncator = LargeResultTruncator(max_string_chars=20)

    result = truncator.truncate([{"id": "a1"}, {"id": "a2"}])

    assert result == {
        "truncated": True,
        "type": "array",
        "items_count": 2,
    }


def test_truncate_top_level_string_to_text_summary() -> None:
    truncator = LargeResultTruncator(max_string_chars=10)

    result = truncator.truncate("0123456789abcdef")

    assert result == {
        "truncated": True,
        "type": "string",
        "text": "0123456...",
        "text_length": 16,
    }
