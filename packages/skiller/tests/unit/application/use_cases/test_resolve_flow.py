from pathlib import Path

import pytest

from skiller.application.use_cases.flow.resolve_flow import (
    ResolveFlowInput,
    ResolveFlowResult,
    ResolveFlowStatus,
    ResolveFlowUseCase,
)
from skiller.domain.flow.flow_reference import FlowReference, ResolvedFlow

pytestmark = pytest.mark.unit


def test_resolve_flow_searches_configured_paths_for_at_reference(
    tmp_path: Path,
) -> None:
    reference = FlowReference(value="@reportes/diario")
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    expected_path = second_root / "reportes" / "diario.yaml"
    expected_path.parent.mkdir(parents=True)
    expected_path.write_text("name: diario", encoding="utf-8")
    use_case = ResolveFlowUseCase(
        home_path=tmp_path / "home",
    )

    result = use_case.execute(
        ResolveFlowInput(
            reference=reference,
            flow_paths=(first_root, second_root),
        )
    )

    assert result == ResolveFlowResult(
        status=ResolveFlowStatus.RESOLVED,
        flow=ResolvedFlow(
            reference=reference,
            flow_path=expected_path.resolve(),
        ),
    )


def test_resolve_flow_uses_first_matching_configured_path(tmp_path: Path) -> None:
    reference = FlowReference(value="@reportes/diario")
    first_path = tmp_path / "first" / "reportes" / "diario.yaml"
    second_path = tmp_path / "second" / "reportes" / "diario.yaml"
    first_path.parent.mkdir(parents=True)
    second_path.parent.mkdir(parents=True)
    first_path.write_text("name: first", encoding="utf-8")
    second_path.write_text("name: second", encoding="utf-8")
    use_case = ResolveFlowUseCase(
        home_path=tmp_path / "home",
    )

    result = use_case.execute(
        ResolveFlowInput(
            reference=reference,
            flow_paths=(first_path.parents[1], second_path.parents[1]),
        )
    )

    assert result.flow is not None
    assert result.flow.flow_path == first_path.resolve()


def test_resolve_flow_searches_same_name_directory_for_simple_at_reference(
    tmp_path: Path,
) -> None:
    reference = FlowReference(value="@flows")
    packaged_root = tmp_path / "apps" / "agents"
    expected_path = packaged_root / "flows" / "flows.yaml"
    expected_path.parent.mkdir(parents=True)
    expected_path.write_text("name: flows", encoding="utf-8")
    use_case = ResolveFlowUseCase(home_path=tmp_path / "home")

    result = use_case.execute(
        ResolveFlowInput(reference=reference, flow_paths=(packaged_root,))
    )

    assert result.status is ResolveFlowStatus.RESOLVED
    assert result.flow is not None
    assert result.flow.flow_path == expected_path.resolve()


def test_resolve_flow_searches_same_name_directory_for_nested_at_reference(
    tmp_path: Path,
) -> None:
    reference = FlowReference(value="@auths/bedrock")
    packaged_root = tmp_path / "apps" / "agents"
    expected_path = packaged_root / "auths" / "bedrock" / "bedrock.yaml"
    expected_path.parent.mkdir(parents=True)
    expected_path.write_text("name: auths/bedrock", encoding="utf-8")
    use_case = ResolveFlowUseCase(home_path=tmp_path / "home")

    result = use_case.execute(
        ResolveFlowInput(reference=reference, flow_paths=(packaged_root,))
    )

    assert result.status is ResolveFlowStatus.RESOLVED
    assert result.flow is not None
    assert result.flow.flow_path == expected_path.resolve()


def test_resolve_flow_prefers_flat_simple_at_reference(tmp_path: Path) -> None:
    reference = FlowReference(value="@flows")
    packaged_root = tmp_path / "apps" / "agents"
    flat_path = packaged_root / "flows.yaml"
    nested_path = packaged_root / "flows" / "flows.yaml"
    nested_path.parent.mkdir(parents=True)
    flat_path.write_text("name: flat", encoding="utf-8")
    nested_path.write_text("name: nested", encoding="utf-8")
    use_case = ResolveFlowUseCase(home_path=tmp_path / "home")

    result = use_case.execute(
        ResolveFlowInput(reference=reference, flow_paths=(packaged_root,))
    )

    assert result.status is ResolveFlowStatus.RESOLVED
    assert result.flow is not None
    assert result.flow.flow_path == flat_path.resolve()


@pytest.mark.parametrize(
    ("reference_value", "relative_path"),
    [
        ("~reportes/diario", Path("reportes/diario.yaml")),
        ("~/reportes/diario", Path("reportes/diario.yaml")),
        ("~/reportes/diario.yml", Path("reportes/diario.yml")),
    ],
)
def test_resolve_flow_validates_home_path(
    tmp_path: Path,
    reference_value: str,
    relative_path: Path,
) -> None:
    reference = FlowReference(value=reference_value)
    home_path = tmp_path / "home"
    expected_path = home_path / relative_path
    expected_path.parent.mkdir(parents=True)
    expected_path.write_text("name: diario", encoding="utf-8")
    use_case = ResolveFlowUseCase(
        home_path=home_path,
    )

    result = use_case.execute(
        ResolveFlowInput(
            reference=reference,
            flow_paths=(),
        )
    )

    assert result == ResolveFlowResult(
        status=ResolveFlowStatus.RESOLVED,
        flow=ResolvedFlow(
            reference=reference,
            flow_path=expected_path.resolve(),
        ),
    )


def test_resolve_flow_accepts_relative_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    expected_path = tmp_path / "reportes" / "diario.yaml"
    expected_path.parent.mkdir()
    expected_path.write_text("name: diario", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    use_case = ResolveFlowUseCase(
        home_path=tmp_path / "home",
    )

    result = use_case.execute(
        ResolveFlowInput(
            reference=FlowReference("./reportes/diario"),
            flow_paths=(),
        )
    )

    assert result.status is ResolveFlowStatus.RESOLVED
    assert result.flow is not None
    assert result.flow.flow_path == expected_path.resolve()


def test_resolve_flow_accepts_absolute_path_without_extension(tmp_path: Path) -> None:
    expected_path = tmp_path / "reportes" / "diario.yaml"
    expected_path.parent.mkdir()
    expected_path.write_text("name: diario", encoding="utf-8")
    use_case = ResolveFlowUseCase(
        home_path=tmp_path / "home",
    )

    result = use_case.execute(
        ResolveFlowInput(
            reference=FlowReference(str(expected_path.with_suffix(""))),
            flow_paths=(),
        )
    )

    assert result.status is ResolveFlowStatus.RESOLVED
    assert result.flow is not None
    assert result.flow.flow_path == expected_path.resolve()


def test_resolve_flow_rejects_unsupported_extension() -> None:
    use_case = ResolveFlowUseCase(
        home_path=Path("/home/fede"),
    )

    result = use_case.execute(
        ResolveFlowInput(
            reference=FlowReference("./reportes/diario.json"),
            flow_paths=(),
        )
    )

    assert result.status is ResolveFlowStatus.INVALID_EXTENSION
    assert result.flow is None
    assert result.error == "Unsupported flow extension: .json"


def test_resolve_flow_returns_not_found_after_searching_all_paths(
    tmp_path: Path,
) -> None:
    reference = FlowReference(value="@missing")
    use_case = ResolveFlowUseCase(
        home_path=tmp_path / "home",
    )

    result = use_case.execute(
        ResolveFlowInput(
            reference=reference,
            flow_paths=(tmp_path / "first", tmp_path / "second"),
        )
    )

    assert result == ResolveFlowResult(
        status=ResolveFlowStatus.NOT_FOUND,
        error="Flow '@missing' not found",
    )
