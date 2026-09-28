"""RQ-17 §3.1/§3.2 — системный инвариант владельца тега (runtime-PR).

Единое межтабличное правило обеих write-surfaces (QueueResource admin +
ServicesApiService), перенесённое из brief `RQ17_SETUP_PATH_BRIEF.md`
(merged `b2888c3a`, #3327) в runtime:

    RESOURCE_SURFACE(tag) :=
          ACTIVE QueueResource(tag)
       OR EXISTS активная resource-owned DailyQueue:
             queue_tag = tag, queue_resource_id IS NOT NULL,
             day >= clinic_today

    RESOURCE_SURFACE(tag) != EMPTY  =>
        >= 1 активная doctorless-услуга (requires_doctor = false)
        AND 0 активных услуг с requires_doctor = true

Serialization: ЛЮБАЯ мутация, способная изменить membership активного
service-set тега или его owner-семантику (QueueResource create/
activation/deactivation; Service create/update/activate/deactivate/
soft-delete, включая ретег `Service.queue_tag`), работает под
transaction-scoped advisory config-lock канонического тега
(`owner_config:tag:{tag}` — конфиг-ключ тега, НЕ дневной
`daily_queue:tag:{tag}:{day}`; прецедент паттерна —
`lock_queue_tag_claim_scope`, `queue_resource_routing.py`). Мульти-теговые
операции (ретег `Service.queue_tag`: old -> new) берут скоупы ВСЕХ
affected-тегов в каноническом sorted-порядке — тот же принцип
упорядочивания, что QD-2E P1 для дневных скоупов; конкурентные
взаимно-обратные ретеги A->B / B->A сериализуются без deadlock.

CRUD-слой (pure lookups + lock helpers): импортируется из services
любого контекста — architecture gate не нарушается.
"""

from __future__ import annotations

from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.crud.queue_resource_routing import _bound_dialect_name
from app.models.online_queue import DailyQueue, QueueResource
from app.models.service import Service

LOCK_KEY_PREFIX = "owner_config:tag:"


class OwnerInvariantViolation(ValueError):
    """Отказ инварианта §3.1: RESOURCE_SURFACE != ∅ при запрещённом
    service-set (0 doctorless или >= 1 requires_doctor), либо попытка
    смены `queue_tag`/`code` по §3.2. Endpoint-слой маппит в HTTP 409."""


def affected_service_tags(old_tag: str | None, new_tag: str | None) -> list[str]:
    """Distinct non-null {old_tag, new_tag} в каноническом sorted-порядке.

    Ретег A->B даёт [A, B] (sorted); переходы с NULL вырождаются в
    одно-теговый список ([A] или [B]).
    """
    return sorted({t for t in (old_tag, new_tag) if t})


def lock_owner_config_scope(db: Session, queue_tag: str) -> None:
    """Transaction-scoped advisory config-lock одного тега (§3.1(б)).

    PostgreSQL: ``pg_advisory_xact_lock(hashtext('owner_config:tag:{tag}'))``
    — конфиг-ключ тега, без дня: сериализует QueueResource-админ и ВСЕ
    Service-мутации тега между собой (анти-TOCTOU check-before-write).
    SQLite (тесты) advisory-локов не имеет — no-op, последовательные
    семантики тестов покрывают поведение (та же паритетность, что у
    `lock_queue_tag_claim_scope`).
    """
    if _bound_dialect_name(db) == "postgresql":
        db.execute(
            sa.text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
            {"k": f"{LOCK_KEY_PREFIX}{queue_tag}"},
        )


def lock_owner_config_scopes(db: Session, queue_tags: list[str]) -> None:
    """Config-локи ВСЕХ affected-тегов в каноническом sorted-порядке (§3.1(в)).

    Одинаковый порядок у конкурентных writers исключает циклическое
    ожидание (deadlock невозможен), а транзакционность локов гарантирует,
    что второй writer входит в критическую секцию только после commit
    первого и валидирует фактическое пост-состояние.
    """
    for tag in sorted(set(queue_tags)):
        lock_owner_config_scope(db, tag)


def tag_service_set_state(db: Session, queue_tag: str) -> tuple[int, int]:
    """(active_doctorless, active_requires_doctor) для тега.

    Активный service-set тега = Service(queue_tag == tag, active = true).
    """
    rows = (
        db.query(Service.requires_doctor, sa.func.count(Service.id))
        .filter(
            Service.queue_tag == queue_tag,
            Service.active.is_(True),
        )
        .group_by(Service.requires_doctor)
        .all()
    )
    counts = {bool(requires): int(count) for requires, count in rows}
    return counts.get(False, 0), counts.get(True, 0)


def resource_surface_exists(db: Session, queue_tag: str, today: date) -> bool:
    """RESOURCE_SURFACE(tag) != ∅ — обе ноги §3.1(а).

    Registry-нога: ACTIVE QueueResource(queue_tag == tag) (exact-tag;
    строка уникальна по queue_tag). DailyQueue-нога: активная
    resource-owned очередь по всему ещё достижимому горизонту
    ``day >= today`` (минимум; booking horizon N дней — допустимая
    верхняя граница, сужение до ``day == today`` ЗАПРЕЩЕНО: предсозданные
    будущие resource-owned очереди — реальная поверхность, прецедент
    force-majeure transfer на завтра).
    """
    registry_active = (
        db.query(QueueResource.id)
        .filter(
            QueueResource.queue_tag == queue_tag,
            QueueResource.active.is_(True),
        )
        .first()
        is not None
    )
    if registry_active:
        return True
    future_resource_queue = (
        db.query(DailyQueue.id)
        .filter(
            DailyQueue.queue_tag == queue_tag,
            DailyQueue.queue_resource_id.isnot(None),
            DailyQueue.active.is_(True),
            DailyQueue.day >= today,
        )
        .first()
    )
    return future_resource_queue is not None


def validate_tag_owner_invariant(
    db: Session, queue_tag: str, today: date
) -> None:
    """Инвариант §3.1 одного тега по его ПОСТ-состоянию.

    Вызывать ПОД локом `lock_owner_config_scope(s)` и ПОСЛЕ flush
    изменений в сессии (flush делает пост-состояние видимым SQL-запросам
    валидации в той же транзакции). RESOURCE_SURFACE(tag) != ∅ требует
    >= 1 активной doctorless-услуги и 0 активных requires_doctor-услуг.
    """
    if not resource_surface_exists(db, queue_tag, today):
        return
    doctorless, requires_doctor = tag_service_set_state(db, queue_tag)
    if requires_doctor > 0 or doctorless < 1:
        raise OwnerInvariantViolation(
            f"Owner invariant violation for tag '{queue_tag}': "
            f"RESOURCE_SURFACE is live (active registry row or "
            f"resource-owned daily queue on day >= {today.isoformat()}), "
            f"but the active service set is "
            f"doctorless={doctorless}, requires_doctor={requires_doctor} "
            f"(expected doctorless >= 1, requires_doctor == 0)"
        )


def validate_service_gate_for_requires_doctor(
    db: Session, queue_tag: str | None, today: date
) -> None:
    """Pre-check создания/перевода услуги в requires_doctor=true (§3.1(а)).

    Быстрый отказ ДО mutate: doctor-required семантика запрещена при
    любой ноге RESOURCE_SURFACE (пины 3–4). Пост-валидация
    `validate_tag_owner_invariant` остаётся обязательной defense-in-depth.
    """
    if not queue_tag:
        return
    if resource_surface_exists(db, queue_tag, today):
        raise OwnerInvariantViolation(
            f"Tag '{queue_tag}' is resource-backed "
            f"(RESOURCE_SURFACE live on day >= {today.isoformat()}): "
            f"requires_doctor=true services are forbidden "
            f"(RQ-17 §3.1)"
        )


def validate_queue_resource_activation(
    db: Session, queue_tag: str, today: date
) -> None:
    """Gate активации QueueResource (POST active=true / PATCH active:true).

    Зеркало `_evaluate_service_gate` миграции 0059 в runtime: тег должен
    быть доказанно doctorless (>= 1 активная doctorless-услуга, 0 активных
    requires_doctor=true), иначе mixed-семантика запрещена (пины 1–2).
    """
    doctorless, requires_doctor = tag_service_set_state(db, queue_tag)
    if requires_doctor > 0 or doctorless < 1:
        raise OwnerInvariantViolation(
            f"Tag '{queue_tag}' is not proven doctorless "
            f"(active doctorless={doctorless}, requires_doctor={requires_doctor}): "
            f"QueueResource activation is rejected (RQ-17 §3.1, "
            f"0059 _evaluate_service_gate precedent)"
        )
