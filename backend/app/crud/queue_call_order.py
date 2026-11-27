"""Canonical priority order for selecting a waiting queue entry."""

from sqlalchemy import func

from app.models.online_queue import OnlineQueueEntry


def waiting_call_order():
    """Compare priority, effective enqueue time, then stable entry identity."""
    return (
        OnlineQueueEntry.priority.desc(),
        func.coalesce(OnlineQueueEntry.queue_time, OnlineQueueEntry.created_at).asc(),
        OnlineQueueEntry.id.asc(),
    )
