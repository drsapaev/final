"""RQ-17 §6(1): минимальный QueueResource admin-контракт (runtime-PR).

Endpoints (Admin-only): ``GET/POST /queue/admin/queue-resources``,
``GET/PATCH /queue/admin/queue-resources/{resource_id}``.

Контракт = brief `RQ17_SETUP_PATH_BRIEF.md` (merged `b2888c3a`, #3327)
буквально:

- §3.1 gate на КАЖДОМ переходе `active=true` (POST `active=true` и
  последующий PATCH `active: true`): тег должен быть доказанно
  doctorless (>= 1 активная doctorless-услуга, 0 активных
  `requires_doctor=true`) — прецедент `_evaluate_service_gate`
  миграции 0059 (пины 1-2); draft (`active=false`) создаётся без gate
  (S-14: услуги/профиль -> draft-ресурс -> активация);
- §3.2 mutability: `code`/`queue_tag` immutable (Update DTO без этих
  полей + extra="forbid" -> 422), `active` — lifecycle-семантика:
  деактивация НЕ осиротяет существующие ресурсные очереди и сама по
  себе ось не возвращает (пин 6 — Service-side gate);
- §3.1(б) serialization: обе write-операции работают под
  transaction-scoped advisory config-lock канонического тега
  (`lock_owner_config_scope`) с валидацией ПОСТ-состояния до commit
  (анти-TOCTOU с параллельными Service-мутациями, пины 5, 9).
"""

from __future__ import annotations

import sqlalchemy as sa
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.api.v1.endpoints.qr_queue._helpers import router
from app.crud.clinic import clinic_today
from app.crud.queue_owner_invariant import (
    OwnerInvariantViolation,
    lock_owner_config_scope,
    validate_queue_resource_activation,
    validate_tag_owner_invariant,
)
from app.models.online_queue import QueueResource
from app.models.user import User
from app.schemas.queue_resources import (
    QueueResourceCreate,
    QueueResourceOut,
    QueueResourceUpdate,
)

_NOT_FOUND = "QueueResource не найден"


def _out(row: QueueResource) -> QueueResourceOut:
    return QueueResourceOut.model_validate(row, from_attributes=True)


def _reject_invariant(exc: OwnerInvariantViolation) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(exc),
    )


@router.get(
    "/admin/queue-resources",
    response_model=list[QueueResourceOut],
    summary="Список QueueResource (реестр ресурсных владельцев тегов)",
    responses={
        401: {"description": "Требуется аутентификация"},
        403: {"description": "Только роль Admin"},
    },
)
def list_queue_resources(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
) -> list[QueueResourceOut]:
    query = db.query(QueueResource).order_by(QueueResource.id.asc())
    if active_only:
        query = query.filter(QueueResource.active.is_(True))
    return [_out(row) for row in query.all()]


@router.get(
    "/admin/queue-resources/{resource_id}",
    response_model=QueueResourceOut,
    summary="QueueResource по id",
    responses={
        401: {"description": "Требуется аутентификация"},
        403: {"description": "Только роль Admin"},
        404: {"description": _NOT_FOUND},
    },
)
def get_queue_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
) -> QueueResourceOut:
    row = db.get(QueueResource, resource_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND
        )
    return _out(row)


@router.post(
    "/admin/queue-resources",
    response_model=QueueResourceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать QueueResource (draft по умолчанию; active=true — через gate §3.1)",
    responses={
        400: {"description": "Невалидный payload"},
        401: {"description": "Требуется аутентификация"},
        403: {"description": "Только роль Admin"},
        409: {"description": "Дубликат code/queue_tag или отказ инварианта §3.1"},
        422: {"description": "Неизвестные поля payload"},
    },
)
def create_queue_resource(
    payload: QueueResourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
) -> QueueResourceOut:
    duplicate = (
        db.query(QueueResource)
        .filter(
            sa.or_(
                QueueResource.code == payload.code,
                QueueResource.queue_tag == payload.queue_tag,
            )
        )
        .first()
    )
    if duplicate is not None:
        field = (
            "code"
            if duplicate.code == payload.code
            else "queue_tag"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"QueueResource {field}='{getattr(payload, field)}' already exists "
                f"(row id={duplicate.id}, tag='{duplicate.queue_tag}')"
            ),
        )

    today = clinic_today(db)
    try:
        # serialization-scope §3.1(б) — наравне с Service-мутациями тега
        lock_owner_config_scope(db, payload.queue_tag)
        if payload.active:
            # gate §3.1 (пины 1-2): тег доказанно doctorless
            validate_queue_resource_activation(db, payload.queue_tag, today)
        row = QueueResource(**payload.model_dump())
        db.add(row)
        db.flush()
        # пост-валидация defense-in-depth (анти-TOCTOU с Service-мутациями)
        validate_tag_owner_invariant(db, payload.queue_tag, today)
        db.commit()
    except OwnerInvariantViolation as exc:
        db.rollback()
        raise _reject_invariant(exc) from exc
    db.refresh(row)
    return _out(row)


@router.patch(
    "/admin/queue-resources/{resource_id}",
    response_model=QueueResourceOut,
    summary="PATCH QueueResource (ordinary-поля; code/queue_tag immutable; active — lifecycle §3.2)",
    responses={
        401: {"description": "Требуется аутентификация"},
        403: {"description": "Только роль Admin"},
        404: {"description": _NOT_FOUND},
        409: {"description": "Отказ инварианта §3.1 при активации"},
        422: {"description": "Попытка изменить immutable code/queue_tag или невалидный payload"},
    },
)
def update_queue_resource(
    resource_id: int,
    payload: QueueResourceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
) -> QueueResourceOut:
    row = db.get(QueueResource, resource_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND
        )

    changes = payload.model_dump(exclude_unset=True)
    today = clinic_today(db)
    try:
        lock_owner_config_scope(db, row.queue_tag)
        if changes.get("active") is True and not row.active:
            # gate §3.1 на повторную активацию (POST active=true и
            # последующий PATCH active: true — равные write-surfaces)
            validate_queue_resource_activation(db, row.queue_tag, today)
        for field, value in changes.items():
            setattr(row, field, value)
        db.flush()
        # пост-валидация: RESOURCE_SURFACE тега по ПОСТ-состоянию
        # (деактивация сама по себе ось не возвращает — пин 6 — и
        # Service-side gate это сериализует тем же локом)
        validate_tag_owner_invariant(db, row.queue_tag, today)
        db.commit()
    except OwnerInvariantViolation as exc:
        db.rollback()
        raise _reject_invariant(exc) from exc
    db.refresh(row)
    return _out(row)
