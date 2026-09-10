from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

from stui.adapter.cli_invoker import CliInvoker
from stui.adapter.events.cli_observe_frame import CliObserveFrame, parse_cli_observe_frame

PROCESS_STOP_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True)
class CliObserveAdapter:
    invoker: CliInvoker = field(default_factory=CliInvoker)

    async def stream(
        self,
        *,
        run_id: str,
        after_sequence: int | None,
        tail: int,
    ) -> AsyncGenerator[CliObserveFrame, None]:
        args = ["observe", run_id, "--tail", str(tail)]
        if after_sequence is not None:
            args.extend(["--after", str(after_sequence)])

        process = await asyncio.create_subprocess_exec(
            *self.invoker.command(*args),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.invoker.environment(),
        )
        assert process.stderr is not None
        stderr_task = asyncio.create_task(process.stderr.read())
        try:
            assert process.stdout is not None
            async for line in process.stdout:
                yield parse_cli_observe_frame(line)

            return_code = await process.wait()
            stderr = (await stderr_task).decode().strip()
            if return_code != 0:
                raise RuntimeError(stderr or "observe command failed")
        finally:
            if process.returncode is None:
                await _stop_process(process)
            if not stderr_task.done():
                stderr_task.cancel()
            await asyncio.gather(stderr_task, return_exceptions=True)


async def _stop_process(process: asyncio.subprocess.Process) -> None:
    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=PROCESS_STOP_TIMEOUT_SECONDS)
    except TimeoutError:
        process.kill()
        await process.wait()
