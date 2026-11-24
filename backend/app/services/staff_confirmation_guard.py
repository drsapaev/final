"""Transaction-scoped authorization and all-free fence for staff confirmations."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.roles import normalize_role_value
from app.models.user import User
from app.models.visit import Visit
from app.services.all_free_guard import AllFreeGuardError
from app.services.encounter_financial_fence import (
    FinancialFenceError,
    lock_group_without_pending,
)
from app.services.patient_subject_lock import (
    PatientSubjectLockError,
    lock_patient_subject,
    require_patient_subject_visibility,
)
from app.services.profile_contact_security import (
    ProfileBearerContext,
    ProfileBearerInvalid,
    check_bearer_expiry,
    check_profile_bearer,
)


def lock_staff_confirmation_actor(db: Session, bearer: ProfileBearerContext) -> User:
    """Pin trusted session visibility, then serialize against logout and role changes."""
    if (not isinstance(bearer, ProfileBearerContext) or bearer.patient_id is not None
        or not isinstance(bearer.jti, str) or not bearer.jti
        or type(bearer.user_id) is not int or bearer.user_id <= 0
        or type(bearer.auth_epoch) is not int or bearer.auth_epoch < 0
        or type(bearer.expires_at) is not int):
        db.rollback()
        raise HTTPException(status_code=401, detail="Сеанс недоступен")
    try:
        # The shared pre-auth boundary must prove full blacklist visibility.
        require_patient_subject_visibility(db)
        if db.get_bind().dialect.name == "sqlite":
            db.connection().exec_driver_sql("UPDATE users SET id=id WHERE 0")
        actor = (db.query(User).filter(User.id == bearer.user_id)
                 .populate_existing().with_for_update(nowait=True).first())
        if actor is None:
            raise ProfileBearerInvalid("Session unavailable")
        check_profile_bearer(db, actor, bearer)
        if not actor.is_superuser and normalize_role_value(actor.role) not in {"admin", "superadmin", "registrar"}:
            raise HTTPException(status_code=403, detail="Доступ запрещён")
        return actor
    except ProfileBearerInvalid:
        db.rollback()
        raise HTTPException(status_code=401, detail="Сеанс недоступен") from None
    except PatientSubjectLockError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    except DBAPIError as exc:
        db.rollback()
        code = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
        if code in {"55P03", "40P01"} or getattr(exc.orig, "sqlite_errorcode", None) in {5, 6}:
            raise HTTPException(status_code=409, detail="Визит занят, повторите запрос") from None
        raise
    except HTTPException:
        db.rollback()
        raise


def lock_staff_confirmation_subjects(
    db: Session, *, bearer: ProfileBearerContext, visit_ids: list[int],
    patient_id: int | None = None,
) -> tuple[User, list[Visit]]:
    """Lock authorized actor, Patient and groups before any confirmation write.

    The caller owns the root transaction and must recheck expiry immediately
    before its commit. Visit and group hints are revalidated under locks.
    """
    if (not visit_ids or any(type(value) is not int or value <= 0 for value in visit_ids)
        or (patient_id is not None and (type(patient_id) is not int or patient_id <= 0))):
        db.rollback()
        raise HTTPException(status_code=404, detail="Визит недоступен")
    ids = sorted(set(visit_ids))
    try:
        actor = lock_staff_confirmation_actor(db, bearer)
        hints = (db.query(Visit.id, Visit.patient_id).filter(Visit.id.in_(ids))
                 .order_by(Visit.id).all())
        if len(hints) != len(ids):
            raise HTTPException(status_code=404, detail="Визит недоступен")
        owners = {row.patient_id for row in hints}
        if len(owners) != 1 or None in owners:
            raise HTTPException(status_code=409, detail="Контекст визита изменился")
        owner_id = owners.pop()
        if patient_id is not None and patient_id != owner_id:
            raise HTTPException(status_code=409, detail="Контекст визита изменился")
        if not lock_patient_subject(db, owner_id):
            raise HTTPException(status_code=409, detail="Контекст пациента изменился")
        for visit_id in ids:
            lock_group_without_pending(db, visit_id)
        visits = (db.query(Visit).filter(Visit.id.in_(ids)).order_by(Visit.id)
                  .populate_existing().all())
        if len(visits) != len(ids) or any(visit.patient_id != owner_id for visit in visits):
            raise HTTPException(status_code=409, detail="Контекст визита изменился")
        # Confirm only a financially identifiable visit. The quote reader
        # validates the locked group, including any benefit allocation; a
        # missing currency is not an implicit choice of today's currency.
        from app.services.payment_invariant_service import PaymentInvariantService

        pricing = PaymentInvariantService(db)
        for visit in visits:
            if not pricing.compute_visit_quote(visit).currency:
                raise HTTPException(status_code=409, detail="Валюта визита требует сверки")
        check_profile_bearer(db, actor, bearer)
        check_bearer_expiry(bearer)
        return actor, visits
    except ProfileBearerInvalid:
        db.rollback()
        raise HTTPException(status_code=401, detail="Сеанс недоступен") from None
    except PatientSubjectLockError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    except (FinancialFenceError, AllFreeGuardError) as exc:
        db.rollback()
        status_code = exc.status_code if isinstance(exc, AllFreeGuardError) else 409
        raise HTTPException(status_code=status_code, detail="Подтверждение временно недоступно") from None
    except DBAPIError as exc:
        db.rollback()
        code = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
        if code in {"55P03", "40P01"} or getattr(exc.orig, "sqlite_errorcode", None) in {5, 6}:
            raise HTTPException(status_code=409, detail="Визит занят, повторите запрос") from None
        raise
    except HTTPException:
        db.rollback()
        raise
