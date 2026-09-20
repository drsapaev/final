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
from sqlalchemy.exc import IntegrityError
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


def _find_duplicate(db: Session, *, code: str, queue_tag: str) -> QueueResource | None:
    return (
        db.query(QueueResource)
        .filter(
            sa.or_(
                QueueResource.code == code,
                QueueResource.queue_tag == queue_tag,
            )
        )
        .first()
    )


def _duplicate_conflict(code: str, queue_tag: str, duplicate: QueueResource) -> HTTPException:
    field = "code" if duplicate.code == code else "queue_tag"
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"QueueResource {field}='{code if field == 'code' else queue_tag}' already exists "
            f"(row id={duplicate.id}, tag='{duplicate.queue_tag}')"
        ),
    )


def _unique_violation_conflict(exc: IntegrityError) -> HTTPException:
    """Гонка POST-ов мимо общего serialization-scope (одинаковый `code` при
    разных `queue_tag` — advisory-локи разные) упирается в UNIQUE-индекс:
    обещанный контракт — 409, а не неперехваченный IntegrityError (500).
    Round-3 owner-ревью P2: mapping уникального нарушения обязателен при
    любом исходе гонки."""
    message = str(getattr(exc, "orig", exc)).lower()
    field = "queue_tag" if "queue_tag" in message else "code"
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"QueueResource {field} already exists (unique constraint "
            "violated by a concurrent create)"
        ),
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
    # быстрый путь: дубликат, уже видимый до лока (Read-side fast fail)
    duplicate = _find_duplicate(
        db, code=payload.code, queue_tag=payload.queue_tag
    )
    if duplicate is not None:
        raise _duplicate_conflict(payload.code, payload.queue_tag, duplicate)

    today = clinic_today(db)
    try:
        # serialization-scope §3.1(б) — наравне с Service-мутациями тега
        lock_owner_config_scope(db, payload.queue_tag)
        # Round-3 P2: RE-CHECK ПОД ЛОКОМ. Дубликат-проверка ДО advisory
        # lock не сериализована: два конкурентных POST одного тега оба
        # видят «дубликата нет», затем второй упирается в UNIQUE
        # (queue_tag/code) -> IntegrityError/500. После входа в
        # serialization-scope перечитываем: дубликат, закоммиченный
        # пока мы ждали лок, здесь видим и отвечаем 409.
        duplicate = _find_duplicate(
            db, code=payload.code, queue_tag=payload.queue_tag
        )
        if duplicate is not None:
            # rollback отпускает txn-scoped advisory lock до выхода
            db.rollback()
            raise _duplicate_conflict(payload.code, payload.queue_tag, duplicate)
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
    except IntegrityError as exc:
        # разные advisory-локи (одинаковый code при разных queue_tag)
        # не сериализуют гонку целиком: UNIQUE-индекс — последняя линия;
        # контракт обещает 409, а не 500 (round-3 P2)
        db.rollback()
        raise _unique_violation_conflict(exc) from exc
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

    # queue_tag immutable (§3.2) — scope лока стабилен; сам лок нужен ДО
    # повторного чтения, поэтому первый read — без блокировки
    tag_scope = row.queue_tag

    changes = payload.model_dump(exclude_unset=True)
    today = clinic_today(db)
    try:
        lock_owner_config_scope(db, tag_scope)
        # Round-3 P2: re-read ПОД row-lock внутри serialization-scope —
        # тот же протокол, что у Service writer-а (get_service_for_update).
        # db.get ДО лока мог вернуть stale identity-map строку: advisory-лок
        # не инвалидирует уже загруженные ORM-объекты, и после ожидания лока
        # решения (gate активации, dirty-set) принимались бы по pre-lock
        # снапшоту — вплоть до потери изменения (stale False->False не
        # помечается dirty, хотя первый writer уже закоммитил True).
        row = (
            db.query(QueueResource)
            .filter(QueueResource.id == resource_id)
            .with_for_update()
            .populate_existing()
            .first()
        )
        if row is None:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND
            )
        if changes.get("active") is True and not row.active:
            # gate §3.1 на повторную активацию (POST active=true и
            # последующий PATCH active: true — равные write-surfaces);
            # решение — по перечитанной под локом строке
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
    except IntegrityError as exc:
        db.rollback()
        raise _unique_violation_conflict(exc) from exc
    db.refresh(row)
    return _out(row)
