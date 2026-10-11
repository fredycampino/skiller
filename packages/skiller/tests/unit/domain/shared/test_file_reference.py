from pathlib import Path

import pytest

from skiller.domain.shared.file_reference import resolve_file_reference, validate_file_reference

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("reference", "environment", "expected"),
    [
        ("./reviewer.json", {}, "/flows/reviewer.json"),
        ("../profile.json", {}, "/profile.json"),
        ("/profiles/../profile.json", {}, "/profile.json"),
        ("~/profile.json", {}, "/home/user/profile.json"),
        ("$PROFILE", {"PROFILE": "reviewer.json"}, "/flows/reviewer.json"),
        ("${BASE}/reviewer.json", {"BASE": "/profiles"}, "/profiles/reviewer.json"),
        (
            "$BASE/${NAME}.json",
            {"BASE": "profiles", "NAME": "reviewer"},
            "/flows/profiles/reviewer.json",
        ),
        ("$PROFILE", {"PROFILE": "$OTHER", "OTHER": "wrong.json"}, "/flows/$OTHER"),
    ],
)
def test_resolve_file_reference(reference, environment, expected) -> None:
    assert resolve_file_reference(
        reference, environment=environment, base_dir=Path("/flows"), home_dir=Path("/home/user")
    ) == Path(expected)


@pytest.mark.parametrize("environment", [{}, {"PROFILE": ""}, {"PROFILE": "  "}])
def test_missing_or_empty_environment_variable_fails(environment) -> None:
    with pytest.raises(ValueError, match="Missing or empty environment variable: PROFILE"):
        resolve_file_reference(
            "$PROFILE", environment=environment, base_dir=Path("/flows"), home_dir=Path("/home")
        )


@pytest.mark.parametrize(
    "reference",
    ["", " ", "${}", "$", "$(pwd)", "${VAR:-x}", "{{inputs.profile}}", "~other/profile"],
)
def test_invalid_reference_syntax(reference) -> None:
    with pytest.raises(ValueError):
        validate_file_reference(reference)
