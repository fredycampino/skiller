from __future__ import annotations

import asyncio

import pytest

from apps.tui.tests.support import FakeEventsPort
from stui.usecase.refresh_events_use_case import RefreshEventsUseCase

pytestmark = pytest.mark.unit


def test_refresh_events_use_case_refreshes_events_port() -> None:
    async def run() -> None:
        events_port = FakeEventsPort()
        use_case = RefreshEventsUseCase(events_port=events_port)

        await use_case.execute()

        assert events_port.refresh_call_count == 1

    asyncio.run(run())
