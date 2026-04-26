from __future__ import annotations

import pytest

from skiller.interfaces.ui.tui_completer import (
    get_command_completion_prefix,
    get_command_suggestions,
)

pytestmark = pytest.mark.unit


def test_get_command_suggestions_returns_all_commands_for_empty_prefix() -> None:
    result = get_command_suggestions("")

    assert "/run" in result
    assert "/help" in result
    assert "/webhooks" in result


def test_get_command_suggestions_filters_by_prefix() -> None:
    result = get_command_suggestions("/r")

    assert result == ["/runs", "/run", "/resume"]


def test_get_command_suggestions_accepts_prefix_without_leading_slash() -> None:
    result = get_command_suggestions("web")

    assert result == ["/webhooks"]


def test_get_command_completion_prefix_returns_prefix_for_first_token() -> None:
    assert get_command_completion_prefix("/ru") == "/ru"


def test_get_command_completion_prefix_returns_none_after_whitespace() -> None:
    assert get_command_completion_prefix("/run notify") is None
    assert get_command_completion_prefix("hola /run") is None
