"""Background task package.

Replaces the previous Celery stub. Will be powered by arq + Redis (see P2.3
in the project plan). For now this module exposes the public task function
signatures so other modules can import them; the actual arq wiring lands in
P2.3.

Pattern:
    from app.tasks import enqueue_reminder, run_data_retention

    await enqueue_reminder(visit_id=123)

Each task function is async and idempotent. The arq worker entry point is
`app.tasks.worker.WorkerSettings` — run with: `arq app.tasks.worker.WorkerSettings`.
"""

from app.tasks.scheduler import (
    enqueue_data_retention,
    enqueue_reminder,
    enqueue_scheduled_report,
)

__all__ = [
    "enqueue_reminder",
    "enqueue_data_retention",
    "enqueue_scheduled_report",
]
