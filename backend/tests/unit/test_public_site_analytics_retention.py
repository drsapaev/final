"""Isolated verification of daily public-site aggregate pruning ownership."""

from datetime import UTC
from unittest.mock import MagicMock

import pytest

from app.db import session
from app.repositories import public_site_analytics_repository
from app.tasks import worker


@pytest.mark.asyncio
async def test_public_site_prune_runs_in_owned_session(monkeypatch):
    session_factory = MagicMock()
    db = session_factory.return_value.__enter__.return_value
    repository = MagicMock()
    repository.return_value.delete_older_than_retention.return_value = 2
    monkeypatch.setattr(session, "SessionLocal", session_factory)
    monkeypatch.setattr(
        public_site_analytics_repository, "PublicSiteAnalyticsRepository", repository
    )

    assert await worker.run_public_site_analytics_retention({}) == 2
    repository.assert_called_once_with(db)
    call = repository.return_value.delete_older_than_retention
    call.assert_called_once()
    assert call.call_args.kwargs["as_of"].tzinfo is UTC
    db.commit.assert_called_once_with()
    session_factory.return_value.__exit__.assert_called_once_with(None, None, None)


def test_public_site_prune_is_an_independent_worker_schedule():
    jobs = [
        job
        for job in worker.WorkerSettings.cron_jobs
        if job.coroutine is worker.run_public_site_analytics_retention
    ]
    assert len(jobs) == 1
    assert jobs[0].minute == 0
    assert jobs[0].hour is None
    assert worker.run_public_site_analytics_retention in worker.WorkerSettings.functions
