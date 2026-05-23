from dataclasses import replace
from pathlib import Path

from skiller.application.tools.files.config import FilesToolRuntimeConfig
from skiller.application.tools.files.models import FilesAction, FilesToolRequest
from skiller.domain.tool.tool_contract import ToolPolicyResult


class FilesToolPolicy:
    def __init__(
        self,
        *,
        config: FilesToolRuntimeConfig,
    ) -> None:
        self.read = self._resolve_roots(config.all + config.read)
        self.write = self._resolve_roots(config.all + config.write)

    def validate(
        self,
        request: FilesToolRequest,
    ) -> ToolPolicyResult[FilesToolRequest]:
        roots = self._roots_for(request.action)
        if not roots:
            return ToolPolicyResult.blocked(
                f"files action '{request.action.value}' is not allowed"
            )

        requested = self._resolve_requested_path(request.path)
        if not self._is_allowed(requested=requested, roots=roots):
            return ToolPolicyResult.blocked(
                f"files path '{request.path}' is outside allowed directories"
            )

        return ToolPolicyResult.allowed(
            replace(
                request,
                effective_path=str(requested),
            )
        )

    def _roots_for(self, action: FilesAction) -> tuple[Path, ...]:
        if action == FilesAction.READ:
            return self.read
        return self.write

    def _resolve_roots(self, roots: tuple[Path, ...]) -> tuple[Path, ...]:
        resolved: list[Path] = []
        for root in roots:
            resolved.append(root.expanduser().resolve(strict=False))
        return tuple(resolved)

    def _resolve_requested_path(self, path: str) -> Path:
        requested = Path(path).expanduser()
        if not requested.is_absolute():
            requested = Path.cwd() / requested
        return requested.resolve(strict=False)

    def _is_allowed(
        self,
        *,
        requested: Path,
        roots: tuple[Path, ...],
    ) -> bool:
        for root in roots:
            if requested == root:
                return True
            try:
                requested.relative_to(root)
            except ValueError:
                continue
            return True
        return False
