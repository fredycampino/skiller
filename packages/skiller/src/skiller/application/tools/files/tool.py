from collections.abc import Mapping
from pathlib import Path
from typing import ClassVar

from skiller.application.tools.files.config import FilesToolRuntimeConfig
from skiller.application.tools.files.models import FilesAction, FilesToolRequest
from skiller.application.tools.files.policy import FilesToolPolicy
from skiller.application.tools.files.runtime_config_mapper import (
    FilesToolRuntimeConfigMapper,
)
from skiller.domain.tool.tool_contract import (
    ConfiguredTool,
    Tool,
    ToolDefinition,
    ToolInput,
    ToolPolicy,
    ToolPolicyResult,
    ToolRequestResult,
    ToolResult,
    ToolResultStatus,
    ToolRuntimeConfig,
    ToolSchema,
)


class FilesTool(
    ToolDefinition[FilesToolRequest],
    Tool[FilesToolRequest],
    ToolPolicy[FilesToolRequest],
    ConfiguredTool[FilesToolRuntimeConfig],
):
    name: ClassVar[str] = "files"
    description: ClassVar[str] = "Read, write, and edit files inside allowed directories"

    def schema(self) -> ToolSchema:
        return ToolSchema(
            value={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read", "write", "edit"],
                    },
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                },
                "required": ["action", "path"],
                "additionalProperties": False,
            }
        )

    def to_runtime_config(
        self,
        raw: Mapping[str, object],
    ) -> FilesToolRuntimeConfig:
        mapper = FilesToolRuntimeConfigMapper()
        return mapper.from_mapping(
            raw=raw,
            definition=type(self),
        )

    def request(self, input: ToolInput) -> ToolRequestResult[FilesToolRequest]:
        try:
            action = FilesAction(input.require_string("action"))
            path = input.require_string("path").strip()
            content = self._optional_raw_string(input, "content")
            old_text = self._optional_raw_string(input, "old_text")
            new_text = self._optional_raw_string(input, "new_text")

            if action == FilesAction.WRITE and content is None:
                raise ValueError(
                    f"Tool call '{input.tool_call_id}' requires string content"
                )
            if action == FilesAction.EDIT:
                if old_text is None or not old_text:
                    raise ValueError(
                        f"Tool call '{input.tool_call_id}' requires non-empty string old_text"
                    )
                if new_text is None:
                    raise ValueError(
                        f"Tool call '{input.tool_call_id}' requires string new_text"
                    )

            return ToolRequestResult.valid(
                FilesToolRequest(
                    action=action,
                    path=path,
                    content=content,
                    old_text=old_text,
                    new_text=new_text,
                )
            )
        except ValueError as exc:
            return ToolRequestResult.invalid(str(exc))

    def policy(
        self,
        *,
        config: ToolRuntimeConfig | None,
        request: FilesToolRequest,
    ) -> ToolPolicyResult[FilesToolRequest]:
        if not isinstance(config, FilesToolRuntimeConfig):
            return ToolPolicyResult.blocked("Tool 'files' requires files runtime config")
        files_policy = FilesToolPolicy(config=config)
        return files_policy.validate(request)

    def run(
        self,
        *,
        config: ToolRuntimeConfig | None,
        request: FilesToolRequest,
    ) -> ToolResult:
        _ = config
        try:
            path = self._effective_path(request)
            if request.action == FilesAction.READ:
                return self._read(request=request, path=path)
            if request.action == FilesAction.WRITE:
                return self._write(request=request, path=path)
            return self._edit(request=request, path=path)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            return ToolResult(
                name=self.name,
                status=ToolResultStatus.FAILED,
                data={
                    "action": request.action.value,
                    "path": request.path,
                },
                text=None,
                error=str(exc),
            )

    def _read(
        self,
        *,
        request: FilesToolRequest,
        path: Path,
    ) -> ToolResult:
        if not path.exists():
            raise ValueError(f"File does not exist: {request.path}")
        if path.is_dir():
            raise ValueError(f"Path is a directory: {request.path}")

        content_bytes = path.read_bytes()
        content = content_bytes.decode("utf-8")

        return ToolResult(
            name=self.name,
            status=ToolResultStatus.COMPLETED,
            data={
                "action": request.action.value,
                "path": request.path,
                "content": content,
                "bytes": len(content_bytes),
            },
            text=f"Read {request.path}",
            error=None,
        )

    def _write(
        self,
        *,
        request: FilesToolRequest,
        path: Path,
    ) -> ToolResult:
        if request.content is None:
            raise ValueError("write requires content")
        if path.exists() and path.is_dir():
            raise ValueError(f"Path is a directory: {request.path}")

        content_bytes = request.content.encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content_bytes)

        return ToolResult(
            name=self.name,
            status=ToolResultStatus.COMPLETED,
            data={
                "action": request.action.value,
                "path": request.path,
                "bytes": len(content_bytes),
            },
            text=f"Wrote {request.path}",
            error=None,
        )

    def _edit(
        self,
        *,
        request: FilesToolRequest,
        path: Path,
    ) -> ToolResult:
        if request.old_text is None or request.new_text is None:
            raise ValueError("edit requires old_text and new_text")
        if not path.exists():
            raise ValueError(f"File does not exist: {request.path}")
        if path.is_dir():
            raise ValueError(f"Path is a directory: {request.path}")

        content_bytes = path.read_bytes()
        content = content_bytes.decode("utf-8")
        matches = content.count(request.old_text)
        if matches == 0:
            raise ValueError("old_text was not found")
        if matches > 1:
            raise ValueError("old_text appears more than once")

        updated = content.replace(request.old_text, request.new_text, 1)
        updated_bytes = updated.encode("utf-8")
        path.write_bytes(updated_bytes)

        return ToolResult(
            name=self.name,
            status=ToolResultStatus.COMPLETED,
            data={
                "action": request.action.value,
                "path": request.path,
                "replacements": 1,
                "bytes": len(updated_bytes),
            },
            text=f"Edited {request.path}",
            error=None,
        )

    def _effective_path(self, request: FilesToolRequest) -> Path:
        if request.effective_path is None:
            raise ValueError("files request was not authorized")
        return Path(request.effective_path)

    def _optional_raw_string(
        self,
        input: ToolInput,
        name: str,
    ) -> str | None:
        value = input.args.get(name)
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"Tool call '{input.tool_call_id}' requires string {name}")
        return value
