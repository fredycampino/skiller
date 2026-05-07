from __future__ import annotations

import pytest

from skiller.interfaces.tui.usecase.autocomplete_use_case import AutocompleteUseCase

pytestmark = pytest.mark.unit


def test_autocomplete_use_case_builds_completion_state_for_slash_prefix() -> None:
    use_case = AutocompleteUseCase()

    state = use_case.execute(text="/ru", cursor_position=3)

    assert state is not None
    assert state.visible is True
    assert state.query == "/ru"
    assert [item.label for item in state.items] == ["run", "runs"]
    assert state.selected_index == 0
    assert state.replace_from == 0
    assert state.replace_to == 3


def test_autocomplete_use_case_hides_exact_command_match() -> None:
    use_case = AutocompleteUseCase()

    state = use_case.execute(text="/run", cursor_position=4)

    assert state is not None
    assert [item.label for item in state.items] == ["runs"]


def test_autocomplete_use_case_hides_non_matching_queries() -> None:
    use_case = AutocompleteUseCase()

    assert use_case.execute(text="/xzx", cursor_position=4) is None


def test_autocomplete_use_case_hides_queries_with_whitespace() -> None:
    use_case = AutocompleteUseCase()

    assert use_case.execute(text="/run chat", cursor_position=9) is None


def test_autocomplete_use_case_suggests_agents_command() -> None:
    use_case = AutocompleteUseCase()

    state = use_case.execute(text="/ag", cursor_position=3)

    assert state is not None
    assert [item.label for item in state.items] == ["agents"]
