"""RQ-17 runtime-PR — негативная матрица инварианта владельца тега §3.1.

Контракт = brief `RQ17_SETUP_PATH_BRIEF.md` (merged `b2888c3a`, #3327):
RESOURCE_SURFACE(tag) = ACTIVE QueueResource(tag) OR активная
resource-owned DailyQueue(queue_tag=tag, day >= clinic_today);
RESOURCE_SURFACE != ∅ требует >= 1 активной doctorless-услуги и 0
активных requires_doctor=true; serialization-scope (transaction-scoped
advisory owner-config lock) на QueueResource-админ и ЛЮБОЙ мутации
Service (create/update/активация/деактивация/soft-delete, включая
двухтеговый протокол ретега `Service.queue_tag`).

Пины 1-15 обязательны в runtime-PR (§3.1/§6 + round-2 owner-ревью
PR #3339). Пины 5/9/12/13/14/15 — конкурентные writer-ы:
двухсоединечные PostgreSQL-пруфы (как
`test_visit_confirmation_claim_concurrency_pg.py`), на SQLite skip.

Round-2 (P1-1): batch-мутация `POST /services/admin/batch-update` —
равноправный writer serialization-scope §3.1 (не setattr-обход):
SQLite-матрица ниже (атомарный reject по owner-sensitive полям,
не-owner batch вне scope, endpoint-маппинг 409) + пин 15 (PG:
batch-writer <-> canonical single writer, sorted, без deadlock).
Round-2 (P1-2): same-Service конкурентные мутации валидируются по
перечитанной locked-строке (SELECT ... FOR UPDATE) — пины 13/14.

Round-3 (owner-ревью PR #3339, P2-волна): пин 16 — explicit `null` для
NOT NULL полей PATCH QueueResource -> 422 (DTO-валидатор, nullable
только `default_cabinet`); пин 17 — дубликат code/queue_tag -> 409;
пин 18 — PATCH перечитывает строку ПОД serialization-scope (stale
identity-map не участвует в решениях); пины 19/20 — конкурентные POST
QueueResource: same-tag (post-lock re-check) и same-code/different-tag
(UNIQUE-нарушение -> 409, не 500), PG-only; пин 21 — batch: audit-строки
внутри batch-транзакции (commit=False), ОДИН commit на изменения +
audit.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.crud.clinic import clinic_today
from app.crud.queue_owner_invariant import (
    OwnerInvariantViolation,
    validate_tag_owner_invariant,
)
from app.models.online_queue import DailyQueue, QueueResource
from app.models.service import Service
from app.models.user import User
from app.schemas.queue_resources import (
    QueueResourceCreate,
    QueueResourceUpdate,
)
from app.services.services_api_service import ServicesApiService

# non-secret placeholder (suite performs no password verification)
_DISABLED_HASH = "!disabled:rq17-owner-invariant"


# ===================== helpers =====================


def _make_user(db: Session, *, username: str, role: str = "Admin") -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password=_DISABLED_HASH,
        role=role,
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_resource(
    db: Session,
    *,
    code: str,
    queue_tag: str,
    active: bool = True,
) -> QueueResource:
    row = QueueResource(
        code=code,
        queue_tag=queue_tag,
        display_name=f"Ресурс {queue_tag}",
        active=active,
        start_number_online=1,
        max_online_per_day=15,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _make_service(
    db: Session,
    *,
    name: str,
    queue_tag: str | None,
    requires_doctor: bool = False,
    active: bool = True,
) -> Service:
    row = Service(
        name=name,
        queue_tag=queue_tag,
        requires_doctor=requires_doctor,
        active=active,
        price=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _make_doctor_queue(
    db: Session,
    *,
    day,
    queue_tag: str,
    doctor_id: int,
    active: bool = True,
) -> DailyQueue:
    row = DailyQueue(
        day=day,
        queue_tag=queue_tag,
        specialist_id=doctor_id,
        queue_resource_id=None,
        active=active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _make_resource_queue(
    db: Session,
    *,
    day,
    queue_tag: str,
    resource_id: int,
    active: bool = True,
) -> DailyQueue:
    row = DailyQueue(
        day=day,
        queue_tag=queue_tag,
        specialist_id=None,
        queue_resource_id=resource_id,
        active=active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ===================== пины 1-2: gate активации QueueResource =====================


def test_pin1_post_active_resource_on_requires_doctor_tag_rejected(
    db_session: Session,
) -> None:
    """Пин 1: POST ресурса (active=true) на тег с активной
    requires_doctor=true-услугой -> reject (409)."""
    admin = _make_user(db_session, username="rq17_admin1")
    _make_service(
        db_session, name="УЗИ с врачом", queue_tag="usound", requires_doctor=True
    )
    from app.api.v1.endpoints.qr_queue import _resources

    with pytest.raises(HTTPException) as exc_info:
        _resources.create_queue_resource(
            payload=QueueResourceCreate(
                code="usound-r",
                queue_tag="usound",
                display_name="УЗИ-ресурс",
                active=True,
            ),
            db=db_session,
            current_user=admin,
        )
    assert exc_info.value.status_code == 409
    assert db_session.query(QueueResource).count() == 0


def test_pin2_post_active_resource_on_mixed_tag_rejected(
    db_session: Session,
) -> None:
    """Пин 2: POST ресурса на mixed-тег (одновременно doctorless и
    requires_doctor) -> reject (409) — mixed-семантика запрещена."""
    admin = _make_user(db_session, username="rq17_admin2")
    _make_service(
        db_session, name="Анализ L01", queue_tag="lab2", requires_doctor=False
    )
    _make_service(
        db_session, name="Анализ с врачом", queue_tag="lab2", requires_doctor=True
    )
    from app.api.v1.endpoints.qr_queue import _resources

    with pytest.raises(HTTPException) as exc_info:
        _resources.create_queue_resource(
            payload=QueueResourceCreate(
                code="lab2-r", queue_tag="lab2", display_name="Лаборатория", active=True
            ),
            db=db_session,
            current_user=admin,
        )
    assert exc_info.value.status_code == 409


def test_pin_draft_resource_creation_without_gate_allowed(
    db_session: Session,
) -> None:
    """S-14 draft: create active=false НЕ требует gate — ось не меняется,
    пока строка не активирована (gate стоит на активации)."""
    admin = _make_user(db_session, username="rq17_admin_draft")
    _make_service(
        db_session, name="Процедура с врачом", queue_tag="physio", requires_doctor=True
    )
    from app.api.v1.endpoints.qr_queue import _resources

    row = _resources.create_queue_resource(
        payload=QueueResourceCreate(
            code="physio-r",
            queue_tag="physio",
            display_name="Физиотерапия",
            active=False,
        ),
        db=db_session,
        current_user=admin,
    )
    assert row.active is False
    # draft не создаёт поверхность: инвариант тега не применим
    validate_tag_owner_invariant(db_session, "physio", clinic_today(db_session))


def test_activation_happy_path_after_doctorless_proof(
    db_session: Session,
) -> None:
    """Целевой путь S-14: doctorless-услуга готова -> draft-ресурс ->
    PATCH active:true проходит gate."""
    admin = _make_user(db_session, username="rq17_admin_ok")
    _make_service(
        db_session, name="Анализ L01", queue_tag="lab9", requires_doctor=False
    )
    from app.api.v1.endpoints.qr_queue import _resources

    row = _resources.create_queue_resource(
        payload=QueueResourceCreate(
            code="lab9-r", queue_tag="lab9", display_name="Лаборатория", active=False
        ),
        db=db_session,
        current_user=admin,
    )
    updated = _resources.update_queue_resource(
        resource_id=row.id,
        payload=QueueResourceUpdate(active=True),
        db=db_session,
        current_user=admin,
    )
    assert updated.active is True


# ===================== пины 3-4: Service requires_doctor на ресурсном теге =====================


def test_pin3_create_requires_doctor_service_on_resource_tag_rejected(
    db_session: Session,
) -> None:
    """Пин 3: Service(requires_doctor=true) на теге с ACTIVE ресурсом
    -> reject."""
    _make_resource(db_session, code="lab3-r", queue_tag="lab3")
    _make_service(db_session, name="Анализ L01", queue_tag="lab3")
    svc = ServicesApiService(db_session)
    with pytest.raises(OwnerInvariantViolation):
        svc.create_service(
            service_data={
                "name": "Анализ с врачом",
                "queue_tag": "lab3",
                "requires_doctor": True,
            }
        )


def test_pin4_flip_doctorless_to_requires_doctor_with_active_resource_rejected(
    db_session: Session,
) -> None:
    """Пин 4: перевод doctorless-услуги в requires_doctor=true при
    существующем ACTIVE ресурсе -> reject."""
    _make_resource(db_session, code="lab4-r", queue_tag="lab4")
    service = _make_service(db_session, name="Анализ L01", queue_tag="lab4")
    svc = ServicesApiService(db_session)
    with pytest.raises(OwnerInvariantViolation):
        svc.update_service(
            service_id=service.id, service_data={"requires_doctor": True}
        )
    db_session.refresh(service)
    assert service.requires_doctor is False


# ===================== пин 6: горизонт поверхности (today OR future) =====================


def test_pin6_deactivation_with_future_resource_queue_keeps_gate(
    db_session: Session,
) -> None:
    """Пин 6 (round-4 горизонт): деактивация строки при существующей
    активной resource-owned DailyQueue на ЗАВТРА -> перевод услуги тега
    в requires_doctor=true отклоняется, пока жива DailyQueue-нога
    (day >= clinic_today), registry-нога не нужна."""
    resource = _make_resource(db_session, code="lab6-r", queue_tag="lab6")
    service = _make_service(db_session, name="Анализ L01", queue_tag="lab6")
    tomorrow = clinic_today(db_session) + timedelta(days=1)
    _make_resource_queue(
        db_session, day=tomorrow, queue_tag="lab6", resource_id=resource.id
    )

    resource.active = False  # деактивация registry-ноги
    db_session.commit()

    svc = ServicesApiService(db_session)
    with pytest.raises(OwnerInvariantViolation):
        svc.update_service(
            service_id=service.id, service_data={"requires_doctor": True}
        )


# ===================== пин 7: lifecycle активации без форка поверхностей =====================


def test_pin7_activation_does_not_fork_fixed_day_surface(
    db_session: Session,
) -> None:
    """Пин 7: активация ресурса при существующей DailyQueue(tag) НЕ
    меняет owner-ось зафиксированного дня; ресурсная ось вступает в
    силу только для дня без зафиксированной поверхности."""
    from app.services.queue_service import queue_service

    resource = _make_resource(db_session, code="lab7-r", queue_tag="lab7", active=False)
    _make_service(db_session, name="Анализ L01", queue_tag="lab7")
    doctor_user = _make_user(db_session, username="rq17_doc7", role="Doctor")
    tomorrow = clinic_today(db_session) + timedelta(days=1)
    doctor_queue_tomorrow = _make_doctor_queue(
        db_session, day=tomorrow, queue_tag="lab7", doctor_id=doctor_user.id
    )

    resource.active = True  # активация ПОСЛЕ зафиксированной завтрашней очереди
    db_session.commit()

    # зафиксированный день НЕ форкается: та же doctor-owned очередь
    surface_tomorrow = queue_service.get_or_create_daily_queue(
        db_session, day=tomorrow, specialist_id=None, queue_tag="lab7"
    )
    assert surface_tomorrow.id == doctor_queue_tomorrow.id
    assert surface_tomorrow.queue_resource_id is None

    # день без зафиксированной поверхности -> ресурсная ось
    surface_today = queue_service.get_or_create_daily_queue(
        db_session,
        day=clinic_today(db_session),
        specialist_id=None,
        queue_tag="lab7",
    )
    assert surface_today.queue_resource_id == resource.id
    assert surface_today.specialist_id is None


# ===================== пины 8-9: soft-delete последней doctorless =====================


def test_pin8_delete_last_doctorless_under_active_resource_rejected(
    db_session: Session,
) -> None:
    """Пин 8: ACTIVE QueueResource + единственная активная doctorless-
    услуга -> DELETE (soft-delete) -> reject: 0 doctorless при живой
    поверхности."""
    _make_resource(db_session, code="lab8-r", queue_tag="lab8")
    service = _make_service(db_session, name="Анализ L01", queue_tag="lab8")
    svc = ServicesApiService(db_session)
    with pytest.raises(OwnerInvariantViolation):
        svc.delete_service(service_id=service.id)
    db_session.rollback()  # отбросить незакоммиченный flush (как get_db teardown)
    db_session.expire_all()
    assert db_session.get(Service, service.id).active is True


def test_delete_doctorless_after_surface_closed_allowed(
    db_session: Session,
) -> None:
    """Обратная сторона пина 8: без RESOURCE_SURFACE (нет registry и
    resource-очередей) DELETE doctorless-услуги легален."""
    service = _make_service(db_session, name="Анализ L01", queue_tag="labX")
    ServicesApiService(db_session).delete_service(service_id=service.id)
    db_session.expire_all()
    assert db_session.get(Service, service.id).active is False


# ===================== пины 10-11: двухтеговый протокол ретега =====================


def test_pin10_retag_moves_last_doctorless_out_of_resource_tag_rejected(
    db_session: Session,
) -> None:
    """Пин 10 (round-5): ACTIVE QueueResource(A) + S — последняя
    doctorless-услуга A -> PUT queue_tag: A->B -> reject: пост-состояние
    A = живая RESOURCE_SURFACE при 0 doctorless. Одно-теговая проверка
    целевого тега B этот переход не видит."""
    _make_resource(db_session, code="ra10", queue_tag="taga10")
    service = _make_service(db_session, name="Анализ A", queue_tag="taga10")
    svc = ServicesApiService(db_session)
    with pytest.raises(OwnerInvariantViolation):
        svc.update_service(
            service_id=service.id, service_data={"queue_tag": "tagb10"}
        )
    db_session.rollback()  # отбросить незакоммиченный flush (как get_db teardown)
    db_session.expire_all()
    assert db_session.get(Service, service.id).queue_tag == "taga10"


def test_pin11_retag_moves_requires_doctor_into_resource_tag_rejected(
    db_session: Session,
) -> None:
    """Пин 11 (round-5): Service(A, requires_doctor=true) -> PUT
    queue_tag: A->B при resource-backed B -> reject: ввозит
    doctor-required услугу в ресурсный тег (верхняя нога)."""
    _make_resource(db_session, code="rb11", queue_tag="tagb11")
    service = _make_service(
        db_session, name="Услуга с врачом", queue_tag="taga11", requires_doctor=True
    )
    svc = ServicesApiService(db_session)
    with pytest.raises(OwnerInvariantViolation):
        svc.update_service(
            service_id=service.id, service_data={"queue_tag": "tagb11"}
        )
    db_session.rollback()  # отбросить незакоммиченный flush (как get_db teardown)
    db_session.expire_all()
    assert db_session.get(Service, service.id).queue_tag == "taga11"


def test_retag_to_from_null_degenerates_to_single_tag(
    db_session: Session,
) -> None:
    """NULL-переходы ретега: A->NULL и NULL->B валидируют единственный
    непустой affected-тег."""
    _make_resource(db_session, code="rn12", queue_tag="tagn12")
    service = _make_service(db_session, name="Анализ N", queue_tag="tagn12")
    svc = ServicesApiService(db_session)
    with pytest.raises(OwnerInvariantViolation):
        svc.update_service(service_id=service.id, service_data={"queue_tag": None})
    # легальный NULL->тег без поверхности проходит
    ok_service = _make_service(db_session, name="Свободная услуга", queue_tag=None)
    svc.update_service(service_id=ok_service.id, service_data={"queue_tag": "tagn12"})
    db_session.expire_all()
    assert db_session.get(Service, ok_service.id).queue_tag == "tagn12"


def test_retag_legal_transfer_passes_both_tags(
    db_session: Session,
) -> None:
    """Легальный ретег A->B (оба тега остаются валидными): resource-
    backed A теряет НЕ последнюю doctorless-услугу, B — без поверхности."""
    _make_resource(db_session, code="ra13", queue_tag="taga13")
    _make_service(db_session, name="Анализ A1", queue_tag="taga13")
    moving = _make_service(db_session, name="Анализ A2", queue_tag="taga13")
    ServicesApiService(db_session).update_service(
        service_id=moving.id, service_data={"queue_tag": "tagb13"}
    )
    db_session.expire_all()
    assert db_session.get(Service, moving.id).queue_tag == "tagb13"
    validate_tag_owner_invariant(db_session, "taga13", clinic_today(db_session))
    validate_tag_owner_invariant(db_session, "tagb13", clinic_today(db_session))


# ===================== §3.2: mutability contract =====================


def test_mutability_patch_queue_tag_and_code_rejected(
    db_session: Session,
) -> None:
    """§3.2 пин: PATCH queue_tag/code на QueueResource -> reject (422,
    extra=forbid); ordinary-поля и lifecycle active применяются."""
    admin = _make_user(db_session, username="rq17_admin_m")
    from app.api.v1.endpoints.qr_queue import _resources

    row = _resources.create_queue_resource(
        payload=QueueResourceCreate(
            code="mut-r", queue_tag="mut", display_name="Мут-ресурс", active=False
        ),
        db=db_session,
        current_user=admin,
    )
    # §3.2 immutable: extra="forbid" отклоняет попытку на уровне DTO
    # (FastAPI маппит ValidationError -> HTTP 422 на входе в endpoint)
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        QueueResourceUpdate.model_validate({"queue_tag": "other"})
    with pytest.raises(ValidationError):
        QueueResourceUpdate.model_validate({"code": "mut-r2"})
    # ordinary PATCH
    updated = _resources.update_queue_resource(
        resource_id=row.id,
        payload=QueueResourceUpdate(
            display_name="Новое имя", start_number_online=3, default_cabinet="101"
        ),
        db=db_session,
        current_user=admin,
    )
    assert updated.display_name == "Новое имя"
    assert updated.start_number_online == 3
    assert updated.default_cabinet == "101"


# ===================== round-2 P1-1: batch writer =====================


def test_batch_update_requires_doctor_on_resource_tag_rejected_atomic(
    db_session: Session,
) -> None:
    """P1-1 regression pin: ACTIVE QueueResource + batch-update
    requires_doctor=true -> 409-класс reject; атомарность: ни одно поле
    batch (включая безобидную цену) не применено; инвариант валиден."""
    _make_resource(db_session, code="btch-r", queue_tag="btag1", active=True)
    service = _make_service(db_session, name="Анализ B1", queue_tag="btag1")
    with pytest.raises(OwnerInvariantViolation):
        ServicesApiService(db_session).batch_update_services(
            service_ids=[service.id],
            updates={"price": 555, "requires_doctor": True},
        )
    db_session.expire_all()
    row = db_session.get(Service, service.id)
    assert row.price == 0
    assert row.requires_doctor is False
    assert row.active is True
    validate_tag_owner_invariant(db_session, "btag1", clinic_today(db_session))


def test_batch_update_deactivate_last_doctorless_rejected(
    db_session: Session,
) -> None:
    """P1-1 pin: batch active=false последней doctorless-услуги при
    живой RESOURCE_SURFACE -> reject (пост-валидация), active сохранён."""
    _make_resource(db_session, code="btch-r2", queue_tag="btag2", active=True)
    service = _make_service(db_session, name="Анализ B2", queue_tag="btag2")
    with pytest.raises(OwnerInvariantViolation):
        ServicesApiService(db_session).batch_update_services(
            service_ids=[service.id], updates={"active": False}
        )
    db_session.expire_all()
    assert db_session.get(Service, service.id).active is True
    validate_tag_owner_invariant(db_session, "btag2", clinic_today(db_session))


def test_batch_update_retag_last_doctorless_out_rejected(
    db_session: Session,
) -> None:
    """P1-1 pin: batch queue_tag away последней doctorless-услуги
    ресурсного тега -> двухтеговый протокол, reject по нижней ноге
    (пин 10 в batch-исполнении)."""
    _make_resource(db_session, code="btch-r3", queue_tag="btag3", active=True)
    service = _make_service(db_session, name="Анализ B3", queue_tag="btag3")
    with pytest.raises(OwnerInvariantViolation):
        ServicesApiService(db_session).batch_update_services(
            service_ids=[service.id], updates={"queue_tag": "btag3-out"}
        )
    db_session.expire_all()
    assert db_session.get(Service, service.id).queue_tag == "btag3"
    validate_tag_owner_invariant(db_session, "btag3", clinic_today(db_session))


def test_batch_update_price_only_skips_invariant_scope(
    db_session: Session,
) -> None:
    """Не-owner-sensitive batch (цена/длительность) не входит в
    serialization-scope: affected-теги = ∅, обычный commit."""
    service_a = _make_service(db_session, name="Услуга A", queue_tag="btag4")
    service_b = _make_service(db_session, name="Услуга B", queue_tag="btag4")
    updated, failed = ServicesApiService(db_session).batch_update_services(
        service_ids=[service_a.id, service_b.id],
        updates={"price": 100, "duration_minutes": 30},
    )
    assert updated == [service_a.id, service_b.id]
    assert failed == []
    db_session.expire_all()
    assert db_session.get(Service, service_a.id).price == 100
    assert db_session.get(Service, service_b.id).duration_minutes == 30


def test_batch_update_flip_without_surface_allowed(db_session: Session) -> None:
    """Позитивный контроль: тег без RESOURCE_SURFACE — owner-sensitive
    batch применяется канонически (локи + валидация проходят)."""
    service = _make_service(db_session, name="Обычная", queue_tag="btag5")
    updated, failed = ServicesApiService(db_session).batch_update_services(
        service_ids=[service.id], updates={"requires_doctor": True}
    )
    assert updated == [service.id]
    assert failed == []
    db_session.expire_all()
    assert db_session.get(Service, service.id).requires_doctor is True


def test_batch_update_missing_ids_reported_found_updated(
    db_session: Session,
) -> None:
    """Не найденные id -> failed_services (прецедент прежнего поведения
    endpoint'а), найденные обновляются в той же транзакции."""
    service = _make_service(db_session, name="Есть", queue_tag="btag6")
    updated, failed = ServicesApiService(db_session).batch_update_services(
        service_ids=[service.id, 10_000_001], updates={"price": 42}
    )
    assert updated == [service.id]
    assert failed == [
        {"service_id": 10_000_001, "error": "Услуга не найдена"}
    ]


def test_batch_update_endpoint_maps_invariant_to_409(
    db_session: Session,
) -> None:
    """Endpoint-контракт round-2: OwnerInvariantViolation из batch
    -> HTTP 409 (атомарно, batch не применён)."""
    import asyncio

    from app.api.v1.endpoints.services_ep._services import (
        ServiceBatchUpdateRequest,
    )
    from app.api.v1.endpoints.services_ep._services import (
        batch_update_services as batch_endpoint,
    )

    _make_resource(db_session, code="btch-r7", queue_tag="btag7", active=True)
    service = _make_service(db_session, name="Анализ B7", queue_tag="btag7")
    admin = _make_user(db_session, username="rq17_admin_b7")
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            batch_endpoint(
                request=ServiceBatchUpdateRequest(
                    service_ids=[service.id], updates={"requires_doctor": True}
                ),
                db=db_session,
                current_user=admin,
            )
        )
    assert exc_info.value.status_code == 409
    db_session.expire_all()
    assert db_session.get(Service, service.id).requires_doctor is False


# ===================== пины 5/9/12: конкурентные writer-ы (PostgreSQL) =====================

def _pg_engine_factory():
    """Схема-per-test PostgreSQL engine (прецедент
    test_visit_confirmation_claim_concurrency_pg.py); SQLite -> None."""
    import os
    import uuid

    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.schema import CreateSchema

    database_url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        return None, None, None
    if os.environ.get("CI", "").lower() != "true" and not (
        url.database or ""
    ).startswith("clinic_test"):
        return None, None, None
    schema = "test_rq17_invariant_" + uuid.uuid4().hex
    admin_engine = create_engine(url, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={
            "options": (
                f"-csearch_path={schema} "
                "-cstatement_timeout=10000 -clock_timeout=8000"
            )
        },
    )
    return engine, admin_engine, schema


def _pg_seed_and_metadata(engine):
    import app.models  # noqa: F401 - register complete metadata
    from app.db.base_class import Base

    Base.metadata.create_all(engine)


def _run_two_writers(writer_a, writer_b) -> tuple[object, object]:
    """Оба writer-а стартуют одновременно; возвращает (outcome_a, outcome_b),
    где outcome = None (успех) или исключение."""
    from concurrent.futures import ThreadPoolExecutor

    def run(fn):
        try:
            fn()
            return None
        except Exception as exc:  # noqa: BLE001 - контракт: ровно один reject
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(run, writer_a)
        future_b = pool.submit(run, writer_b)
        return future_a.result(), future_b.result()


def _wait_lock_waits(engine, timeout: float = 5.0) -> bool:
    """Best-effort детекция ожидающего лока бэкенда (writer2 стоит на
    row-lock writer1). Исход пинов 13/14 детерминирован и без сигнала
    (READ COMMITTED + row-lock на первом чтении writer2); сигнал лишь
    укрепляет доказательную ценность stale-window-оркестрации."""
    import time

    import sqlalchemy as sa

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            waiting = conn.execute(
                sa.text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() "
                    "AND wait_event_type = 'Lock'"
                )
            ).scalar_one()
        if waiting:
            return True
        time.sleep(0.05)
    return False


def _pg_cleanup(admin_engine, engine, schema) -> None:
    from sqlalchemy.schema import DropSchema

    engine.dispose()
    with admin_engine.begin() as connection:
        # cascade=True: прецедент claim-concurrency; без него DROP падает
        # DependentObjectsStillExist, пока пул не освободил все соединения
        connection.execute(DropSchema(schema, cascade=True))
    admin_engine.dispose()


def test_pin5_concurrent_resource_activation_vs_requires_doctor_flip(
    db_session: Session,
) -> None:
    """Пин 5: конкурентные «активация ресурса <-> перевод услуги в
    requires_doctor=true» из легального стартового состояния: ровно один
    writer отклоняется; финальное состояние удовлетворяет инварианту."""
    engine, admin_engine, schema = _pg_engine_factory()
    if engine is None:
        pytest.skip("requires PostgreSQL (CI or disposable clinic_test db)")
    try:
        _pg_seed_and_metadata(engine)
        sessionmaker = __import__(
            "sqlalchemy.orm", fromlist=["sessionmaker"]
        ).sessionmaker
        SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
        setup = SessionLocal()
        admin = _make_user(setup, username="rq17_pg_admin5")
        resource = _make_resource(
            setup, code="lab5-r", queue_tag="lab5", active=False
        )
        service = _make_service(setup, name="Анализ L01", queue_tag="lab5")
        setup.commit()
        setup.close()

        from app.api.v1.endpoints.qr_queue import _resources

        def writer_activation():
            s = SessionLocal()
            try:
                _resources.update_queue_resource(
                    resource_id=resource.id,
                    payload=QueueResourceUpdate(active=True),
                    db=s,
                    current_user=admin,
                )
            finally:
                s.close()

        def writer_flip():
            s = SessionLocal()
            try:
                ServicesApiService(s).update_service(
                    service_id=service.id, service_data={"requires_doctor": True}
                )
            finally:
                s.close()

        outcome_a, outcome_b = _run_two_writers(writer_activation, writer_flip)
        outcomes = [outcome_a, outcome_b]
        rejected = [o for o in outcomes if o is not None]
        assert len(rejected) == 1, f"expected exactly one reject, got {outcomes!r}"
        assert all(
            isinstance(o, (OwnerInvariantViolation, HTTPException)) for o in rejected
        )
        check = SessionLocal()
        try:
            validate_tag_owner_invariant(
                check, "lab5", clinic_today(check)
            )
        finally:
            check.close()
    finally:
        _pg_cleanup(admin_engine, engine, schema)


def test_pin9_concurrent_resource_activation_vs_delete_last_doctorless(
    db_session: Session,
) -> None:
    """Пин 9: конкурентные «активация ресурса <-> DELETE последней
    doctorless-услуги»: ровно один reject; mixed/orphan недостижим."""
    engine, admin_engine, schema = _pg_engine_factory()
    if engine is None:
        pytest.skip("requires PostgreSQL (CI or disposable clinic_test db)")
    try:
        _pg_seed_and_metadata(engine)
        sessionmaker = __import__(
            "sqlalchemy.orm", fromlist=["sessionmaker"]
        ).sessionmaker
        SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
        setup = SessionLocal()
        admin = _make_user(setup, username="rq17_pg_admin9")
        resource = _make_resource(
            setup, code="lab9z-r", queue_tag="lab9z", active=False
        )
        service = _make_service(setup, name="Анализ L01", queue_tag="lab9z")
        setup.commit()
        setup.close()

        from app.api.v1.endpoints.qr_queue import _resources

        def writer_activation():
            s = SessionLocal()
            try:
                _resources.update_queue_resource(
                    resource_id=resource.id,
                    payload=QueueResourceUpdate(active=True),
                    db=s,
                    current_user=admin,
                )
            finally:
                s.close()

        def writer_delete():
            s = SessionLocal()
            try:
                ServicesApiService(s).delete_service(service_id=service.id)
            finally:
                s.close()

        outcome_a, outcome_b = _run_two_writers(writer_activation, writer_delete)
        outcomes = [outcome_a, outcome_b]
        rejected = [o for o in outcomes if o is not None]
        assert len(rejected) == 1, f"expected exactly one reject, got {outcomes!r}"
        check = SessionLocal()
        try:
            validate_tag_owner_invariant(check, "lab9z", clinic_today(check))
        finally:
            check.close()
    finally:
        _pg_cleanup(admin_engine, engine, schema)


def test_pin12_concurrent_reverse_retags_sorted_locks_no_deadlock(
    db_session: Session,
) -> None:
    """Пин 12: конкурентные взаимно-обратные ретеги A->B и B->A (оба
    writer-а берут owner-config-локи {A,B} в одном sorted-порядке):
    deadlock невозможен, критические секции сериализованы, оба легальных
    переноса применяются; mixed-состояние недостижимо."""
    engine, admin_engine, schema = _pg_engine_factory()
    if engine is None:
        pytest.skip("requires PostgreSQL (CI or disposable clinic_test db)")
    try:
        _pg_seed_and_metadata(engine)
        sessionmaker = __import__(
            "sqlalchemy.orm", fromlist=["sessionmaker"]
        ).sessionmaker
        SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
        setup = SessionLocal()
        _make_resource(setup, code="ra12", queue_tag="taga12")
        _make_resource(setup, code="rb12", queue_tag="tagb12")
        _make_service(setup, name="Остаток A", queue_tag="taga12")
        _make_service(setup, name="Остаток B", queue_tag="tagb12")
        s1 = _make_service(setup, name="Переезд A->B", queue_tag="taga12")
        s2 = _make_service(setup, name="Переезд B->A", queue_tag="tagb12")
        setup.commit()
        setup.close()

        def writer_a_to_b():
            s = SessionLocal()
            try:
                ServicesApiService(s).update_service(
                    service_id=s1.id, service_data={"queue_tag": "tagb12"}
                )
            finally:
                s.close()

        def writer_b_to_a():
            s = SessionLocal()
            try:
                ServicesApiService(s).update_service(
                    service_id=s2.id, service_data={"queue_tag": "taga12"}
                )
            finally:
                s.close()

        outcome_a, outcome_b = _run_two_writers(writer_a_to_b, writer_b_to_a)
        assert outcome_a is None and outcome_b is None, (
            f"sorted-order serialization must complete both legal retags, "
            f"got {outcome_a!r}, {outcome_b!r}"
        )
        check = SessionLocal()
        try:
            check.expire_all()
            assert check.get(Service, s1.id).queue_tag == "tagb12"
            assert check.get(Service, s2.id).queue_tag == "taga12"
            today = clinic_today(check)
            validate_tag_owner_invariant(check, "taga12", today)
            validate_tag_owner_invariant(check, "tagb12", today)
        finally:
            check.close()
    finally:
        _pg_cleanup(admin_engine, engine, schema)


def test_pin13_same_service_concurrent_retag_vs_requires_doctor_flip(
    db_session: Session,
) -> None:
    """Пин 13 (round-2 P1-2): same-Service конкурентные «ретег A->B» и
    «requires_doctor false->true» при resource-backed B. Writer2 стартует
    ДО commit writer1 (stale-window): row-level serialization (SELECT ...
    FOR UPDATE) обязывает writer2 вычислить affected_tags из перечитанной
    locked-строки (queue_tag=B), поэтому forbidden mixed-финал
    (B live + активная requires_doctor) недостижим: ровно один reject,
    инвариант валиден."""
    engine, admin_engine, schema = _pg_engine_factory()
    if engine is None:
        pytest.skip("requires PostgreSQL (CI or disposable clinic_test db)")
    try:
        import threading

        import sqlalchemy as sa

        _pg_seed_and_metadata(engine)
        sessionmaker = __import__(
            "sqlalchemy.orm", fromlist=["sessionmaker"]
        ).sessionmaker
        SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
        setup = SessionLocal()
        _make_resource(setup, code="rq13-r", queue_tag="rq13b", active=True)
        _make_service(setup, name="Остаток B", queue_tag="rq13b")
        service = _make_service(
            setup, name="Переезд rq13a->rq13b", queue_tag="rq13a"
        )
        setup.commit()
        setup.close()

        row_locked = threading.Event()
        commit_go = threading.Event()
        writer1_outcome: list[object] = []

        def writer1_midflight() -> None:
            """Эмуляция writer1 в mid-flight: канонический lock-footprint
            (advisory {A,B} sorted + row-lock Service) и некоммитнутый
            ретег; commit -- только по сигналу, когда writer2 уже стоит
            на row-lock."""
            conn = engine.connect()
            try:
                tx = conn.begin()
                try:
                    for tag in ("rq13a", "rq13b"):
                        conn.execute(
                            sa.text(
                                "SELECT pg_advisory_xact_lock(hashtext(:k))"
                            ),
                            {"k": f"owner_config:tag:{tag}"},
                        )
                    conn.execute(
                        sa.text(
                            "SELECT id FROM services WHERE id = :i FOR UPDATE"
                        ),
                        {"i": service.id},
                    )
                    conn.execute(
                        sa.text(
                            "UPDATE services SET queue_tag = 'rq13b' "
                            "WHERE id = :i"
                        ),
                        {"i": service.id},
                    )
                    row_locked.set()
                    if not commit_go.wait(timeout=15):
                        raise RuntimeError("pin13: writer1 commit gate timed out")
                    tx.commit()
                except Exception:
                    tx.rollback()
                    raise
            finally:
                conn.close()

        def writer1_wrapped() -> None:
            try:
                writer1_midflight()
                writer1_outcome.append(None)
            except Exception as exc:  # noqa: BLE001
                writer1_outcome.append(exc)

        thread1 = threading.Thread(target=writer1_wrapped)
        thread1.start()
        assert row_locked.wait(timeout=15), (
            "pin13: writer1 never reached row lock"
        )

        def writer2_flip() -> object:
            try:
                s = SessionLocal()
                try:
                    ServicesApiService(s).update_service(
                        service_id=service.id,
                        service_data={"requires_doctor": True},
                    )
                finally:
                    s.close()
                return None
            except Exception as exc:  # noqa: BLE001
                return exc

        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=1) as pool:
            future2 = pool.submit(writer2_flip)
            _wait_lock_waits(engine)
            commit_go.set()
            outcome2 = future2.result()
        thread1.join(timeout=15)
        assert writer1_outcome == [None], (
            f"pin13: writer1 must commit the retag, got {writer1_outcome!r}"
        )
        assert isinstance(outcome2, OwnerInvariantViolation), (
            "pin13: writer2 must be rejected on the actual post-lock tag B, "
            f"got {outcome2!r}"
        )
        check = SessionLocal()
        try:
            check.expire_all()
            row = check.get(Service, service.id)
            assert row.queue_tag == "rq13b"
            assert row.requires_doctor is False
            assert row.active is True
            validate_tag_owner_invariant(check, "rq13b", clinic_today(check))
        finally:
            check.close()
    finally:
        _pg_cleanup(admin_engine, engine, schema)


def test_pin14_same_service_concurrent_retag_vs_delete(
    db_session: Session,
) -> None:
    """Пин 14 (round-2 P1-2): same-Service «ретег A->B» <-> «soft-delete».
    Валидация delete обязана использовать фактический post-lock тег
    (B resource-backed; S после ретега — последняя doctorless B), а не
    stale pre-lock тег A (без поверхности — выглядел бы легальным):
    stale-семантика осиротила бы B. Row-level serialization -> ровно
    один reject, active сохранён, инвариант валиден."""
    engine, admin_engine, schema = _pg_engine_factory()
    if engine is None:
        pytest.skip("requires PostgreSQL (CI or disposable clinic_test db)")
    try:
        import threading

        import sqlalchemy as sa

        _pg_seed_and_metadata(engine)
        sessionmaker = __import__(
            "sqlalchemy.orm", fromlist=["sessionmaker"]
        ).sessionmaker
        SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
        setup = SessionLocal()
        _make_resource(setup, code="rq14-r", queue_tag="rq14b", active=True)
        service = _make_service(
            setup, name="Последняя doctorless", queue_tag="rq14a"
        )
        setup.commit()
        setup.close()

        row_locked = threading.Event()
        commit_go = threading.Event()
        writer1_outcome: list[object] = []

        def writer1_midflight() -> None:
            conn = engine.connect()
            try:
                tx = conn.begin()
                try:
                    for tag in ("rq14a", "rq14b"):
                        conn.execute(
                            sa.text(
                                "SELECT pg_advisory_xact_lock(hashtext(:k))"
                            ),
                            {"k": f"owner_config:tag:{tag}"},
                        )
                    conn.execute(
                        sa.text(
                            "SELECT id FROM services WHERE id = :i FOR UPDATE"
                        ),
                        {"i": service.id},
                    )
                    conn.execute(
                        sa.text(
                            "UPDATE services SET queue_tag = 'rq14b' "
                            "WHERE id = :i"
                        ),
                        {"i": service.id},
                    )
                    row_locked.set()
                    if not commit_go.wait(timeout=15):
                        raise RuntimeError("pin14: writer1 commit gate timed out")
                    tx.commit()
                except Exception:
                    tx.rollback()
                    raise
            finally:
                conn.close()

        def writer1_wrapped() -> None:
            try:
                writer1_midflight()
                writer1_outcome.append(None)
            except Exception as exc:  # noqa: BLE001
                writer1_outcome.append(exc)

        thread1 = threading.Thread(target=writer1_wrapped)
        thread1.start()
        assert row_locked.wait(timeout=15), (
            "pin14: writer1 never reached row lock"
        )

        def writer2_delete() -> object:
            try:
                s = SessionLocal()
                try:
                    ServicesApiService(s).delete_service(service_id=service.id)
                finally:
                    s.close()
                return None
            except Exception as exc:  # noqa: BLE001
                return exc

        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=1) as pool:
            future2 = pool.submit(writer2_delete)
            _wait_lock_waits(engine)
            commit_go.set()
            outcome2 = future2.result()
        thread1.join(timeout=15)
        assert writer1_outcome == [None], (
            f"pin14: writer1 must commit the retag, got {writer1_outcome!r}"
        )
        assert isinstance(outcome2, OwnerInvariantViolation), (
            "pin14: delete must be rejected on the actual post-lock tag B, "
            f"got {outcome2!r}"
        )
        check = SessionLocal()
        try:
            check.expire_all()
            row = check.get(Service, service.id)
            assert row.queue_tag == "rq14b"
            assert row.active is True
            validate_tag_owner_invariant(check, "rq14b", clinic_today(check))
        finally:
            check.close()
    finally:
        _pg_cleanup(admin_engine, engine, schema)


def test_pin15_batch_writer_vs_single_retag_sorted_no_deadlock(
    db_session: Session,
) -> None:
    """Пин 15 (round-2 P1-1): batch-writer (ретег S1 rq15a->rq15b через
    batch_update_services) против canonical single writer (ретег S2
    rq15b->rq15a): row-locks + owner-config-локи {A,B} в sorted-порядке
    с обеих сторон — сериализация без deadlock, оба легальных переноса
    применены, инварианты обоих тегов валидны."""
    engine, admin_engine, schema = _pg_engine_factory()
    if engine is None:
        pytest.skip("requires PostgreSQL (CI or disposable clinic_test db)")
    try:
        _pg_seed_and_metadata(engine)
        sessionmaker = __import__(
            "sqlalchemy.orm", fromlist=["sessionmaker"]
        ).sessionmaker
        SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
        setup = SessionLocal()
        _make_service(setup, name="Остаток A", queue_tag="rq15a")
        _make_service(setup, name="Остаток B", queue_tag="rq15b")
        s1 = _make_service(setup, name="Переезд A->B", queue_tag="rq15a")
        s2 = _make_service(setup, name="Переезд B->A", queue_tag="rq15b")
        setup.commit()
        setup.close()

        def writer_batch_a_to_b():
            s = SessionLocal()
            try:
                ServicesApiService(s).batch_update_services(
                    service_ids=[s1.id], updates={"queue_tag": "rq15b"}
                )
            finally:
                s.close()

        def writer_single_b_to_a():
            s = SessionLocal()
            try:
                ServicesApiService(s).update_service(
                    service_id=s2.id, service_data={"queue_tag": "rq15a"}
                )
            finally:
                s.close()

        outcome_a, outcome_b = _run_two_writers(
            writer_batch_a_to_b, writer_single_b_to_a
        )
        assert outcome_a is None and outcome_b is None, (
            f"sorted-order serialization must complete both legal retags, "
            f"got {outcome_a!r}, {outcome_b!r}"
        )
        check = SessionLocal()
        try:
            check.expire_all()
            assert check.get(Service, s1.id).queue_tag == "rq15b"
            assert check.get(Service, s2.id).queue_tag == "rq15a"
            today = clinic_today(check)
            validate_tag_owner_invariant(check, "rq15a", today)
            validate_tag_owner_invariant(check, "rq15b", today)
        finally:
            check.close()
    finally:
        _pg_cleanup(admin_engine, engine, schema)


# ===================== round-3 P2-волна: пины 16-21 =====================


def test_pin16_patch_explicit_null_not_null_field_rejected_422() -> None:
    """Пин 16 (round-3 P2): explicit `null` для NOT NULL полей
    PATCH-схемы -> ValidationError (FastAPI -> 422 на входе); nullable
    только `default_cabinet`; absent-поля остаются «нет изменения»."""
    from pydantic import ValidationError

    for field in ("display_name", "start_number_online", "max_online_per_day", "active"):
        with pytest.raises(ValidationError) as exc_info:
            QueueResourceUpdate.model_validate({field: None})
        # причина — наш валидатор, а не неудавшееся приведение типа
        assert "NOT NULL" in str(exc_info.value)

    # nullable-поле: explicit null легален (очистка кабинета)
    cleared = QueueResourceUpdate.model_validate({"default_cabinet": None})
    assert cleared.model_dump(exclude_unset=True) == {"default_cabinet": None}

    # absent = нет изменения (exclude_unset-семантика endpoint'а)
    assert QueueResourceUpdate().model_dump(exclude_unset=True) == {}


def test_pin17_create_duplicate_code_or_tag_409(
    db_session: Session,
) -> None:
    """Пин 17 (round-3 P2): POST QueueResource с уже существующим
    queue_tag или code -> 409 (быстрый путь ДО лока)."""
    admin = _make_user(db_session, username="rq17_admin_dup")
    _make_resource(db_session, code="dup-r", queue_tag="duptag")
    from app.api.v1.endpoints.qr_queue import _resources

    with pytest.raises(HTTPException) as exc_info:
        _resources.create_queue_resource(
            payload=QueueResourceCreate(
                code="dup-r2", queue_tag="duptag", display_name="Дубль-тег"
            ),
            db=db_session,
            current_user=admin,
        )
    assert exc_info.value.status_code == 409
    assert "queue_tag" in exc_info.value.detail

    with pytest.raises(HTTPException) as exc_info:
        _resources.create_queue_resource(
            payload=QueueResourceCreate(
                code="dup-r", queue_tag="othertag", display_name="Дубль-код"
            ),
            db=db_session,
            current_user=admin,
        )
    assert exc_info.value.status_code == 409
    assert "code" in exc_info.value.detail
    assert db_session.query(QueueResource).count() == 1


def test_pin18_patch_rereads_row_under_serialization_scope(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Пин 18 (round-3 P2): PATCH перечитывает строку под row-lock после
    входа в serialization-scope — gate активации решает по ФАКТИЧЕСКОМУ
    состоянию строки, а не по stale identity-map снапшоту."""
    admin = _make_user(db_session, username="rq17_admin_stale")
    _make_service(db_session, name="Анализ ST1", queue_tag="stale1")
    row = _make_resource(
        db_session, code="stale1-r", queue_tag="stale1", active=True
    )

    # внешний writer деактивирует строку ПОЗА identity-map db_session
    from sqlalchemy.orm import sessionmaker

    Other = sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    other = Other()
    try:
        other.query(QueueResource).filter(QueueResource.id == row.id).update(
            {"active": False}
        )
        other.commit()
    finally:
        other.close()

    # db_session держит stale active=True; контроль: запрос ДО endpoint
    # возвращает ТОТ ЖЕ identity-map объект, который db.get в endpoint'е
    # отдаст без обращения к БД — именно этот stale снапшот re-read под
    # локом обязан перезатереть (populate_existing)
    stale_view = db_session.query(QueueResource).filter(
        QueueResource.id == row.id
    ).first()
    assert stale_view.active is True  # stale снапшот ещё жив

    from app.api.v1.endpoints.qr_queue import _resources

    calls = []
    real_gate = _resources.validate_queue_resource_activation

    def gate_spy(db, queue_tag, today):
        calls.append(queue_tag)
        return real_gate(db, queue_tag, today)

    monkeypatch.setattr(_resources, "validate_queue_resource_activation", gate_spy)

    # PATCH active=true при ФАКТИЧЕСКИ деактивированной строке: re-read под
    # локом обязан вернуть active=False -> gate вызывается ровно один раз
    updated = _resources.update_queue_resource(
        resource_id=row.id,
        payload=QueueResourceUpdate(active=True),
        db=db_session,
        current_user=admin,
    )
    assert calls == ["stale1"], (
        "gate must run against the re-read (post-lock) row state"
    )
    assert updated.active is True


def test_pin19_concurrent_post_same_tag_second_waits_then_409(
    db_session: Session,
) -> None:
    """Пин 19 (round-3 P2): конкурентные POST одного queue_tag — второй
    writer после ожидания advisory-лока перечитывает дубликат ПОД локом и
    получает 409 (не IntegrityError/500). PG-only."""
    engine, admin_engine, schema = _pg_engine_factory()
    if engine is None:
        pytest.skip("requires PostgreSQL (CI or disposable clinic_test db)")
    try:
        _pg_seed_and_metadata(engine)
        sessionmaker = __import__(
            "sqlalchemy.orm", fromlist=["sessionmaker"]
        ).sessionmaker
        SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
        setup = SessionLocal()
        admin = _make_user(setup, username="rq17_pg_admin19")
        setup.commit()
        setup.close()

        from app.api.v1.endpoints.qr_queue import _resources

        def writer_tag():
            s = SessionLocal()
            try:
                _resources.create_queue_resource(
                    payload=QueueResourceCreate(
                        code="race19-a", queue_tag="race19", display_name="A"
                    ),
                    db=s,
                    current_user=admin,
                )
            finally:
                s.close()

        def writer_tag2():
            s = SessionLocal()
            try:
                _resources.create_queue_resource(
                    payload=QueueResourceCreate(
                        code="race19-b", queue_tag="race19", display_name="B"
                    ),
                    db=s,
                    current_user=admin,
                )
            finally:
                s.close()

        outcome_a, outcome_b = _run_two_writers(writer_tag, writer_tag2)
        outcomes = [outcome_a, outcome_b]
        succeeded = [o for o in outcomes if o is None]
        rejected = [o for o in outcomes if o is not None]
        assert len(succeeded) == 1, f"expected exactly one success, got {outcomes!r}"
        assert len(rejected) == 1, f"expected exactly one reject, got {outcomes!r}"
        assert isinstance(rejected[0], HTTPException), type(rejected[0])
        assert rejected[0].status_code == 409

        check = SessionLocal()
        try:
            assert check.query(QueueResource).count() == 1
        finally:
            check.close()
    finally:
        _pg_cleanup(admin_engine, engine, schema)


def test_pin20_concurrent_post_same_code_different_tags_unique_maps_409(
    db_session: Session,
) -> None:
    """Пин 20 (round-3 P2): конкурентные POST с ОДИНАКОВЫМ code при
    РАЗНЫХ queue_tag — advisory-локи разные, serialization-scope не общий;
    проигравший упирается в UNIQUE-индекс и ДОЛЖЕН получить 409 (маппинг
    IntegrityError), а не 500. PG-only."""
    engine, admin_engine, schema = _pg_engine_factory()
    if engine is None:
        pytest.skip("requires PostgreSQL (CI or disposable clinic_test db)")
    try:
        _pg_seed_and_metadata(engine)
        sessionmaker = __import__(
            "sqlalchemy.orm", fromlist=["sessionmaker"]
        ).sessionmaker
        SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
        setup = SessionLocal()
        admin = _make_user(setup, username="rq17_pg_admin20")
        setup.commit()
        setup.close()

        from app.api.v1.endpoints.qr_queue import _resources

        def writer_tag1():
            s = SessionLocal()
            try:
                _resources.create_queue_resource(
                    payload=QueueResourceCreate(
                        code="race20", queue_tag="race20a", display_name="A"
                    ),
                    db=s,
                    current_user=admin,
                )
            finally:
                s.close()

        def writer_tag2():
            s = SessionLocal()
            try:
                _resources.create_queue_resource(
                    payload=QueueResourceCreate(
                        code="race20", queue_tag="race20b", display_name="B"
                    ),
                    db=s,
                    current_user=admin,
                )
            finally:
                s.close()

        outcome_a, outcome_b = _run_two_writers(writer_tag1, writer_tag2)
        outcomes = [outcome_a, outcome_b]
        succeeded = [o for o in outcomes if o is None]
        rejected = [o for o in outcomes if o is not None]
        assert len(succeeded) == 1, f"expected exactly one success, got {outcomes!r}"
        assert len(rejected) == 1, f"expected exactly one reject, got {outcomes!r}"
        # IntegrityError НЕ допускается наружу — только маппнутый 409
        assert isinstance(rejected[0], HTTPException), type(rejected[0])
        assert rejected[0].status_code == 409

        check = SessionLocal()
        try:
            assert check.query(QueueResource).count() == 1
        finally:
            check.close()
    finally:
        _pg_cleanup(admin_engine, engine, schema)


def test_pin21_batch_audit_rows_share_single_commit_transaction(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Пин 21 (round-3 P2): batch_update_services пишет audit-строки ВНУТРИ
    своей транзакции (commit=False), и ОДИН commit применяет изменения +
    audit атомарно. Внутренний commit audit-хелпера ломал single-commit
    границу: первый же audit коммитил batch и отпускал локи до конца
    критической секции."""
    from sqlalchemy import inspect as sa_inspect

    from app.models.service_audit import ServiceAuditLog
    from app.services.service_audit_service import ServiceAuditService

    service = _make_service(db_session, name="Анализ AUD1", queue_tag="audtag1")

    original = ServiceAuditService.log_service_change
    calls = []

    def spy(self, *, commit=True, **kwargs):
        calls.append({"commit": commit, "in_txn": self.db.in_transaction()})
        return original(self, commit=commit, **kwargs)

    monkeypatch.setattr(ServiceAuditService, "log_service_change", spy)

    ServicesApiService(db_session).batch_update_services(
        service_ids=[service.id],
        updates={"price": 777},
        comment="single-commit boundary pin",
    )

    assert calls, "audit rows must be written for every batch member"
    assert all(call["commit"] is False for call in calls), calls
    # каждая audit-строка создавалась в ОТКРЫТОЙ транзакции batch'а
    # (legacy-поведение: после внутреннего commit первого audit-вызова
    # последующие вызовы видели бы in_txn=False)
    assert all(call["in_txn"] is True for call in calls), calls

    # audit-строки закоммичены вместе с изменением
    count = db_session.query(ServiceAuditLog).filter(
        ServiceAuditLog.service_id == service.id
    ).count()
    assert count == 1
    db_session.expire_all()
    assert db_session.get(Service, service.id).price == 777
    audit_row = (
        db_session.query(ServiceAuditLog)
        .filter(ServiceAuditLog.service_id == service.id)
        .one()
    )
    assert audit_row.comment == "Batch update: single-commit boundary pin"
    assert "price" in (audit_row.changes or {})
    assert not sa_inspect(audit_row).pending
