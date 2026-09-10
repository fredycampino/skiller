from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from stui.adapter.events import cli_observe_adapter
from stui.adapter.events.cli_observe_adapter import CliObserveAdapter

pytestmark = pytest.mark.unit


@dataclass
class FakeInvoker:
    command_calls: list[tuple[str, ...]]

    def command(self, *args: str) -> list[str]:
        self.command_calls.append(args)
        return ["skiller", *args]

    def environment(self) -> dict[str, str]:
        return {"TEST": "1"}


class FakeStream:
    def __init__(self, lines: list[bytes]) -> None:
        self.lines = list(lines)

    def __aiter__(self) -> FakeStream:
        return self

    async def __anext__(self) -> bytes:
        if not self.lines:
            raise StopAsyncIteration
        return self.lines.pop(0)


class FakeStderr:
    def __init__(self, value: bytes = b"") -> None:
        self.value = value

    async def read(self) -> bytes:
        return self.value


class FakeProcess:
    def __init__(self, *, lines: list[bytes], return_code: int, stderr: bytes = b"") -> None:
        self.stdout = FakeStream(lines)
        self.stderr = FakeStderr(stderr)
        self.returncode: int | None = return_code
        self.terminated = False
        self.killed = False

    async def wait(self) -> int:
        assert self.returncode is not None
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


class BlockingStderr:
    def __init__(self, *, blocks_after_cancellation: bool = False) -> None:
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.finished = asyncio.Event()
        self.release = asyncio.Event()
        self.blocks_after_cancellation = blocks_after_cancellation

    async def read(self) -> bytes:
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            if self.blocks_after_cancellation:
                await self.release.wait()
            raise
        finally:
            self.finished.set()


class ActiveProcess:
    def __init__(
        self,
        *,
        finishes_after_terminate: bool,
        blocks_stderr_after_cancellation: bool = False,
    ) -> None:
        self.stdout = FakeStream(
            [
                b'{"kind":"start","version":1,"run_id":"run-1","requested_after":null,"effective_after":0,"last_sequence":0,"tail":100,"truncated":false}\n'
            ]
        )
        self.stderr = BlockingStderr(
            blocks_after_cancellation=blocks_stderr_after_cancellation
        )
        self.returncode: int | None = None
        self.finishes_after_terminate = finishes_after_terminate
        self.terminated = False
        self.killed = False
        self.wait_calls = 0

    async def wait(self) -> int:
        self.wait_calls += 1
        if self.killed:
            self.returncode = -9
            return self.returncode
        if self.terminated and self.finishes_after_terminate:
            self.returncode = 0
            return self.returncode
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


def test_cli_observe_adapter_starts_jsonl_stream_with_cursor_and_tail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def create_process(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        assert args == (
            "skiller",
            "observe",
            "run-1",
            "--tail",
            "25",
            "--after",
            "12",
        )
        assert kwargs["env"] == {"TEST": "1"}
        return FakeProcess(
            lines=[
                b'{"kind":"start","version":1,"run_id":"run-1","requested_after":12,"effective_after":12,"last_sequence":12,"tail":25,"truncated":false}\n'
            ],
            return_code=0,
        )

    async def run() -> None:
        monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)
        invoker = FakeInvoker(command_calls=[])
        adapter = CliObserveAdapter(invoker=invoker)  # type: ignore[arg-type]

        frames = [
            frame
            async for frame in adapter.stream(
                run_id="run-1",
                after_sequence=12,
                tail=25,
            )
        ]

        assert invoker.command_calls == [
            ("observe", "run-1", "--tail", "25", "--after", "12")
        ]
        assert frames[0].kind == "start"

    asyncio.run(run())


def test_cli_observe_adapter_raises_runtime_error_for_failed_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def create_process(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        _ = args, kwargs
        return FakeProcess(lines=[], return_code=1, stderr=b"run not found")

    async def run() -> None:
        monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)
        adapter = CliObserveAdapter(invoker=FakeInvoker(command_calls=[]))  # type: ignore[arg-type]

        with pytest.raises(RuntimeError, match="run not found"):
            async for _ in adapter.stream(
                run_id="missing",
                after_sequence=None,
                tail=100,
            ):
                pass

    asyncio.run(run())


def test_cli_observe_adapter_terminates_active_process_when_stream_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = ActiveProcess(finishes_after_terminate=True)

    async def create_process(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        _ = args, kwargs
        return process

    async def run() -> None:
        monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)
        adapter = CliObserveAdapter(invoker=FakeInvoker(command_calls=[]))  # type: ignore[arg-type]
        stream = adapter.stream(run_id="run-1", after_sequence=None, tail=100)

        await anext(stream)
        await asyncio.wait_for(process.stderr.started.wait(), timeout=1)
        await stream.aclose()
        await asyncio.wait_for(process.stderr.cancelled.wait(), timeout=1)

        assert process.terminated
        assert not process.killed
        assert process.wait_calls == 1

    asyncio.run(run())


def test_cli_observe_adapter_kills_process_when_terminate_times_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = ActiveProcess(finishes_after_terminate=False)

    async def create_process(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        _ = args, kwargs
        return process

    async def run() -> None:
        monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)
        monkeypatch.setattr(cli_observe_adapter, "PROCESS_STOP_TIMEOUT_SECONDS", 0.01)
        adapter = CliObserveAdapter(invoker=FakeInvoker(command_calls=[]))  # type: ignore[arg-type]
        stream = adapter.stream(run_id="run-1", after_sequence=None, tail=100)

        await anext(stream)
        await asyncio.wait_for(process.stderr.started.wait(), timeout=1)
        await stream.aclose()
        await asyncio.wait_for(process.stderr.cancelled.wait(), timeout=1)

        assert process.terminated
        assert process.killed
        assert process.wait_calls == 2

    asyncio.run(run())


def test_cli_observe_adapter_waits_for_stderr_task_when_stream_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = ActiveProcess(
        finishes_after_terminate=True,
        blocks_stderr_after_cancellation=True,
    )

    async def create_process(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        _ = args, kwargs
        return process

    async def run() -> None:
        monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)
        adapter = CliObserveAdapter(invoker=FakeInvoker(command_calls=[]))  # type: ignore[arg-type]
        stream = adapter.stream(run_id="run-1", after_sequence=None, tail=100)

        await anext(stream)
        await asyncio.wait_for(process.stderr.started.wait(), timeout=1)
        closing = asyncio.create_task(stream.aclose())
        await asyncio.wait_for(process.stderr.cancelled.wait(), timeout=1)

        assert not closing.done()

        process.stderr.release.set()
        await closing

        assert process.stderr.finished.is_set()

    asyncio.run(run())
