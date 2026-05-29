from pathlib import Path

import pytest

from skiller.application.agent.tools.tool_manager import ToolManager, ToolPrepareFailure
from skiller.application.agent.tools.tool_manager_model import AgentToolRequest
from skiller.application.tools.files import (
    FilesAction,
    FilesTool,
    FilesToolRequest,
    FilesToolRuntimeConfig,
)
from skiller.domain.tool.tool_contract import ToolInput, ToolResultStatus

pytestmark = pytest.mark.unit


def test_files_tool_maps_read_request() -> None:
    tool = FilesTool()

    result = tool.request(
        _input(
            {
                "action": "read",
                "path": "notes.txt",
            }
        )
    )

    assert result.ok is True
    assert result.request == FilesToolRequest(
        action=FilesAction.READ,
        path="notes.txt",
    )


def test_files_tool_accepts_empty_write_content() -> None:
    tool = FilesTool()

    result = tool.request(
        _input(
            {
                "action": "write",
                "path": "notes.txt",
                "content": "",
            }
        )
    )

    assert result.ok is True
    assert result.request == FilesToolRequest(
        action=FilesAction.WRITE,
        path="notes.txt",
        content="",
    )


def test_files_tool_accepts_empty_edit_replacement() -> None:
    tool = FilesTool()

    result = tool.request(
        _input(
            {
                "action": "edit",
                "path": "notes.txt",
                "old_text": "remove me",
                "new_text": "",
            }
        )
    )

    assert result.ok is True
    assert result.request == FilesToolRequest(
        action=FilesAction.EDIT,
        path="notes.txt",
        old_text="remove me",
        new_text="",
    )


def test_files_tool_rejects_invalid_request() -> None:
    tool = FilesTool()

    result = tool.request(
        _input(
            {
                "action": "write",
                "path": "notes.txt",
            }
        )
    )

    assert result.ok is False
    assert result.error == "Tool call 'call-1' requires string content"


def test_files_tool_rejects_edit_without_non_empty_old_text() -> None:
    tool = FilesTool()

    result = tool.request(
        _input(
            {
                "action": "edit",
                "path": "notes.txt",
                "old_text": "",
                "new_text": "replacement",
            }
        )
    )

    assert result.ok is False
    assert result.error == "Tool call 'call-1' requires non-empty string old_text"


def test_files_tool_maps_runtime_config() -> None:
    tool = FilesTool()

    config = tool.to_runtime_config(
        {
            "read": ["."],
            "write": ["src"],
            "all": ["shared"],
        }
    )

    assert config == FilesToolRuntimeConfig(
        definition=FilesTool,
        read=(Path("."),),
        write=(Path("src"),),
        all=(Path("shared"),),
    )


def test_files_tool_rejects_unsupported_runtime_config_fields() -> None:
    tool = FilesTool()

    with pytest.raises(ValueError, match="unsupported config fields: delete"):
        tool.to_runtime_config({"delete": ["."]})


def test_files_tool_policy_allows_path_inside_root(tmp_path) -> None:
    tool = FilesTool()
    root = tmp_path / "workspace"
    root.mkdir()

    result = tool.policy(
        config=FilesToolRuntimeConfig(
            definition=FilesTool,
            read=(root,),
        ),
        request=FilesToolRequest(
            action=FilesAction.READ,
            path=str(root / "notes.txt"),
        ),
    )

    assert result.ok is True
    assert result.request is not None
    assert result.request.effective_path == str(root / "notes.txt")


def test_files_tool_policy_blocks_path_outside_root(tmp_path) -> None:
    tool = FilesTool()
    root = tmp_path / "workspace"
    root.mkdir()

    result = tool.policy(
        config=FilesToolRuntimeConfig(
            definition=FilesTool,
            read=(root,),
        ),
        request=FilesToolRequest(
            action=FilesAction.READ,
            path=str(tmp_path / "outside.txt"),
        ),
    )

    assert result.ok is False
    assert result.error == (
        f"files path '{tmp_path / 'outside.txt'}' is outside allowed directories"
    )


def test_files_tool_writes_and_reads_text(tmp_path) -> None:
    tool = FilesTool()
    target = tmp_path / "workspace" / "nested" / "notes.txt"

    write_result = tool.run(
        config=None,
        request=FilesToolRequest(
            action=FilesAction.WRITE,
            path="nested/notes.txt",
            content="hello",
            effective_path=str(target),
        ),
    )
    read_result = tool.run(
        config=None,
        request=FilesToolRequest(
            action=FilesAction.READ,
            path="nested/notes.txt",
            effective_path=str(target),
        ),
    )

    assert write_result.status == ToolResultStatus.COMPLETED
    assert write_result.data == {
        "action": "write",
        "path": "nested/notes.txt",
        "bytes": 5,
    }
    assert read_result.status == ToolResultStatus.COMPLETED
    assert read_result.data == {
        "action": "read",
        "path": "nested/notes.txt",
        "content": "hello",
        "bytes": 5,
    }
    assert read_result.text == "Read nested/notes.txt"


def test_files_tool_edits_exactly_one_match(tmp_path) -> None:
    tool = FilesTool()
    target = tmp_path / "notes.txt"
    target.write_text("before\nkeep\n", encoding="utf-8")

    result = tool.run(
        config=None,
        request=FilesToolRequest(
            action=FilesAction.EDIT,
            path="notes.txt",
            old_text="before",
            new_text="after",
            effective_path=str(target),
        ),
    )

    assert result.status == ToolResultStatus.COMPLETED
    assert result.data == {
        "action": "edit",
        "path": "notes.txt",
        "replacements": 1,
        "bytes": 11,
    }
    assert target.read_text(encoding="utf-8") == "after\nkeep\n"


def test_files_tool_edit_fails_when_old_text_is_not_unique(tmp_path) -> None:
    tool = FilesTool()
    target = tmp_path / "notes.txt"
    target.write_text("same\nsame\n", encoding="utf-8")

    result = tool.run(
        config=None,
        request=FilesToolRequest(
            action=FilesAction.EDIT,
            path="notes.txt",
            old_text="same",
            new_text="changed",
            effective_path=str(target),
        ),
    )

    assert result.status == ToolResultStatus.FAILED
    assert result.error == "old_text appears more than once"


def test_files_tool_manager_prepare_applies_config_and_policy(tmp_path) -> None:
    tool = FilesTool()
    router = ToolManager([tool])
    root = tmp_path / "workspace"
    root.mkdir()
    target = root / "notes.txt"

    result = router.prepare(
        AgentToolRequest(
            run_id="run-1",
            step_id="support_agent",
            context_id="thread-1",
            turn_id="turn-1",
            tool_call_id="call-1",
            tool="files",
            args={
                "action": "read",
                "path": str(target),
            },
            allowed_tools=["files"],
            runtime_config=FilesToolRuntimeConfig(
                definition=FilesTool,
                read=(root,),
            ),
        )
    )

    assert result.ok is True
    assert result.prepared is not None
    assert result.prepared.name == "files"
    assert result.prepared.request == FilesToolRequest(
        action=FilesAction.READ,
        path=str(target),
        effective_path=str(target),
    )


def test_files_tool_manager_prepare_blocks_missing_roots(tmp_path) -> None:
    tool = FilesTool()
    router = ToolManager([tool])

    result = router.prepare(
        AgentToolRequest(
            run_id="run-1",
            step_id="support_agent",
            context_id="thread-1",
            turn_id="turn-1",
            tool_call_id="call-1",
            tool="files",
            args={
                "action": "read",
                "path": str(tmp_path / "notes.txt"),
            },
            allowed_tools=["files"],
            runtime_config=FilesToolRuntimeConfig(
                definition=FilesTool,
            ),
        )
    )

    assert result.ok is False
    assert result.error == ToolPrepareFailure.POLICY_BLOCKED
    assert result.error_message == "files action 'read' is not allowed"


def _input(args: dict[str, object]) -> ToolInput:
    return ToolInput(
        run_id="run-1",
        step_id="support_agent",
        tool_call_id="call-1",
        args=args,
    )
