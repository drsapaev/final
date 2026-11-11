"""Regression tests for scheduling standalone queue WebSocket broadcasts.

The public sync helper must call the manager's *synchronous* broadcast method
once. WSManager.broadcast already owns scheduling through _dispatch.
All event names, rooms and queue identifiers are synthetic.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.ws import queue_ws


@pytest.mark.asyncio
async def test_queue_update_calls_sync_manager_once_in_running_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = SimpleNamespace(broadcast=Mock(return_value=None))
    monkeypatch.setattr(queue_ws, "ws_manager", manager)

    queue_ws.broadcast_queue_update(
        " specialist_42 ",
        " 2026-11-10 ",
        "queue_update",
        {"entry_id": 17, "action": "synthetic"},
    )

    manager.broadcast.assert_called_once_with(
        "specialist_42::2026-11-10",
        {
            "type": "queue_update",
            "room": "specialist_42::2026-11-10",
            "data": {"entry_id": 17, "action": "synthetic"},
        },
    )


@pytest.mark.asyncio
async def test_queue_update_uses_manager_dispatch_without_double_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delivered: list[tuple[str, dict]] = []
    tasks: list[asyncio.Task] = []

    async def send(room: str, message: dict) -> None:
        delivered.append((room, message))

    def broadcast(room: str, message: dict) -> None:
        # Stand-in for WSManager.broadcast: it schedules internally and
        # returns None (never an awaitable).
        tasks.append(asyncio.create_task(send(room, message)))

    monkeypatch.setattr(
        queue_ws, "ws_manager", SimpleNamespace(broadcast=broadcast)
    )

    queue_ws.broadcast_queue_update(
        "specialist_7", "2026-11-10", "patient_called"
    )
    await asyncio.gather(*tasks)

    assert len(tasks) == 1
    assert delivered == [
        (
            "specialist_7::2026-11-10",
            {
                "type": "patient_called",
                "room": "specialist_7::2026-11-10",
                "data": {},
            },
        )
    ]


def test_queue_update_without_running_loop_skips_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = SimpleNamespace(broadcast=Mock(return_value=None))
    monkeypatch.setattr(queue_ws, "ws_manager", manager)

    # A normal synchronous caller has no running event loop. Preserve
    # the existing best-effort skip rather than dispatching on a new loop.
    queue_ws.broadcast_queue_update(
        "specialist_5", "2026-11-10", "queue_update"
    )

    manager.broadcast.assert_not_called()
