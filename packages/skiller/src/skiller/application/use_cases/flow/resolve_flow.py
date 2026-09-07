from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from skiller.domain.flow.flow_reference import FlowReference, ResolvedFlow


class ResolveFlowStatus(str, Enum):
    RESOLVED = "RESOLVED"
    NOT_FOUND = "NOT_FOUND"
    INVALID_EXTENSION = "INVALID_EXTENSION"


@dataclass(frozen=True)
class ResolveFlowResult:
    status: ResolveFlowStatus
    flow: ResolvedFlow | None = None
    error: str | None = None


@dataclass(frozen=True)
class ResolveFlowInput:
    reference: FlowReference
    flow_paths: tuple[Path, ...]


class ResolveFlowUseCase:
    def __init__(self, home_path: Path) -> None:
        self.home_path = home_path

    def execute(self, request: ResolveFlowInput) -> ResolveFlowResult:
        reference = request.reference
        reference_value = reference.value
        search_configured_paths = reference_value.startswith("@")

        if reference_value.startswith("~"):
            relative_value = reference_value.removeprefix("~").removeprefix("/")
            reference_path = self.home_path / relative_value
        else:
            path_value = reference_value.removeprefix("@")
            reference_path = Path(path_value)

        if not reference_path.suffix:
            reference_path = reference_path.with_suffix(".yaml")
        elif reference_path.suffix.lower() not in {".yaml", ".yml"}:
            return ResolveFlowResult(
                status=ResolveFlowStatus.INVALID_EXTENSION,
                error=f"Unsupported flow extension: {reference_path.suffix}",
            )

        candidate_paths = (reference_path,)
        if search_configured_paths:
            candidates: list[Path] = []
            for configured_path in request.flow_paths:
                candidates.append(configured_path / reference_path)
                candidates.append(
                    configured_path
                    / reference_path.parent
                    / reference_path.stem
                    / reference_path.name
                )
            candidate_paths = tuple(candidates)

        for candidate_path in candidate_paths:
            if not candidate_path.is_file():
                continue

            flow = ResolvedFlow(
                reference=reference,
                flow_path=candidate_path.resolve(),
            )
            return ResolveFlowResult(
                status=ResolveFlowStatus.RESOLVED,
                flow=flow,
            )

        return ResolveFlowResult(
            status=ResolveFlowStatus.NOT_FOUND,
            error=f"Flow '{reference_value}' not found",
        )
