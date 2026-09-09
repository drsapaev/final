"""Codex R15 #3092 (P2): изоляция сбоя тега при pre-creation очередей.

Полный откат сеанса в except-ветке стирал очереди, созданные предыдущими
итерациями этого же вызова, а created_count их уже учёл: отчёт
«создано N» расходился с реальностью и ломал гарантию pre-creation.
SAVEPOINT изолирует сбойнувший тег — предыдущие создания остаются.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue
from app.models.service import Service
from app.services import queue_service as queue_service_module
from app.services.morning_assignment import MorningAssignmentService

pytestmark = [pytest.mark.integration]


def _tagged_service(db: Session, *, code: str, tag: str) -> Service:
    service = Service(
        code=code,
        service_code=code,
        name=f"R15 {code}",
        price=10000.00,
        duration_minutes=30,
        active=True,
        requires_doctor=False,
        queue_tag=tag,
        department_key=tag,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def test_tag_failure_does_not_erase_earlier_precreated_queues(
    db_session: Session,
    test_doctor: Doctor,
    monkeypatch,
):
    """Вторая очередь падает → первая ОБЯЗАНА остаться в сеансе; счётчик
    честный; сбойнувший тег не оставляет мусора."""
    if db_session.get_bind().dialect.name == "sqlite":
        pytest.skip("SAVEPOINT isolation is a PostgreSQL semantics test (gate_d convention)")
    _tagged_service(db_session, code="R15-ISO-1", tag="r15_iso_tag_1")
    _tagged_service(db_session, code="R15-ISO-2", tag="r15_iso_tag_2")

    real_get_or_create = queue_service_module.queue_service.get_or_create_daily_queue
    calls: list[str] = []

    def flaky_get_or_create(db, *, day, specialist_id, queue_tag):
        calls.append(queue_tag)
        if len(calls) == 2:
            raise RuntimeError("simulated failure on the second tag")
        return real_get_or_create(
            db, day=day, specialist_id=specialist_id, queue_tag=queue_tag
        )

    monkeypatch.setattr(
        queue_service_module.queue_service,
        "get_or_create_daily_queue",
        flaky_get_or_create,
    )

    created = MorningAssignmentService(db_session).ensure_daily_queues_for_all_tags(
        date.today()
    )

    assert calls == ["r15_iso_tag_1", "r15_iso_tag_2"], (
        "the failing tag must not prevent later tags from being attempted"
    )
    assert created == 1, "created_count must reflect only queues that exist"
    assert (
        db_session.query(DailyQueue)
        .filter(DailyQueue.queue_tag == "r15_iso_tag_1", DailyQueue.active.is_(True))
        .count()
        == 1
    ), "the earlier tag's queue must SURVIVE the later tag's failure"
    assert (
        db_session.query(DailyQueue)
        .filter(DailyQueue.queue_tag == "r15_iso_tag_2", DailyQueue.active.is_(True))
        .count()
        == 0
    ), "the failed tag must not leave a half-created queue behind"
