"""Review bound manual price requests under the shared financial locks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import exists, or_, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.roles import is_doctor_role_spelling, normalize_role_value
from app.models.audit import AuditLog
from app.models.billing import Invoice
from app.models.clinic import Doctor
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.patient import Patient
from app.models.payment import Payment, PaymentVisit
from app.models.payment_invoice import PaymentInvoiceVisit
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.authorization.staff import staff_authorization_service
from app.services.encounter_financial_fence import (
    FinancialFenceError,
    lock_financial_group,
    requote_draft_invoice_prices,
)
from app.services.money_input import MoneyInputError, parse_money
from app.services.patient_subject_lock import (
    PatientSubjectLockError,
    lock_patient_subject,
    require_patient_subject_visibility,
)
from app.services.profile_contact_security import (
    ProfileBearerInvalid,
    check_bearer_expiry,
    check_profile_bearer,
)
from app.services.visit_invitation_delivery import (
    InvitationContextChanged,
    InvitationRuntimeUnavailable,
    stage_price_approval_recovery,
)


@dataclass
class PriceOverrideApprovalError(Exception):
    """Domain error translated to HTTP by every delegating endpoint."""

    status_code: int
    detail: str


PENDING_STATUS = "pending"
APPROVED_STATUS = "approved"
REJECTED_STATUS = "rejected"

# REGPRICE-BE-003 (audit 3892, group 16): shared refusal text for a SECOND
# pending override on the same visit/service. The creation-side probe itself
# lives on the repositories (``has_pending_override``) so the dental/derma
# services stay repository-boundary compliant — they must never touch the
# raw session (enforced by tests/unit/test_service_repository_boundary.py).
PENDING_DUPLICATE_DETAIL = (
    "Для этой услуги уже есть запрос изменения цены, ожидающий "
    "одобрения — дождитесь его обработки или отклоните дубликат."
)


class PriceOverrideApprovalService:
    """Single SSOT for approve/reject decisions on ``DoctorPriceOverride``."""

    def __init__(self, db: Session):
        self.db = db

    def _assert_no_financial_exposure(self, visit_id: int) -> None:
        """Inspect selected persisted exposure; never an approval authority.

        This diagnostic does not cover every provider record or in-flight
        invoice writer. Passing it cannot make price mutation safe.
        """
        linked_group_invoice = (
            self.db.query(PaymentInvoiceVisit.id)
            .filter(PaymentInvoiceVisit.visit_id == visit_id)
            .first()
        )
        linked_manual_invoice = (
            self.db.query(Invoice.id).filter(Invoice.visit_id == visit_id).first()
        )
        if linked_group_invoice is not None or linked_manual_invoice is not None:
            raise PriceOverrideApprovalError(
                409,
                "Счёт связан с визитом; изменение цены требует согласованного перерасчёта счёта",
            )

        legacy_link = exists().where(
            PaymentVisit.payment_id == Payment.id,
            PaymentVisit.visit_id == visit_id,
        )
        payments = (
            self.db.query(Payment)
            .filter(or_(Payment.visit_id == visit_id, legacy_link))
            .populate_existing()
            .all()
        )
        for payment in payments:
            status = str(payment.status or "").strip().lower()
            if status not in {"paid", "completed", "refunded", "cancelled", "void"}:
                raise PriceOverrideApprovalError(
                    409, "По визиту есть незавершённый платёж; изменение цены недоступно"
                )
            # A local cancellation does not rule out a later provider debit.
            if status in {"cancelled", "void"}:
                raise PriceOverrideApprovalError(
                    409, "Статус отменённого платежа требует сверки с провайдером"
                )
            try:
                amount = Decimal(str(payment.amount))
                refunded = Decimal(str(payment.refunded_amount or 0))
            except (ValueError, ArithmeticError):
                raise PriceOverrideApprovalError(409, "Невозможно проверить возврат платежа") from None
            if (
                not amount.is_finite()
                or not refunded.is_finite()
                or amount < 0
                or refunded < 0
                or refunded > amount
                or amount - refunded > 0
            ):
                raise PriceOverrideApprovalError(
                    409, "По визиту есть оплаченный остаток; сначала оформите возврат"
                )

    def _lock_request(self, override_id, action, approver_id, bearer):
        if bearer.user_id != approver_id or bearer.patient_id is not None:
            raise ProfileBearerInvalid("Bearer session unavailable")
        if self.db.get_bind().dialect.name == "sqlite":
            # FOR UPDATE is ignored on SQLite; reserve the single writer
            # before reading any row which drives the decision.
            self.db.execute(text("UPDATE users SET id=id WHERE 0"))
        if action == "approve":
            require_patient_subject_visibility(self.db)
        # Authenticate the locked live actor before revealing whether an
        # override exists. The dependency's earlier check can race a logout
        # or role change before this transaction reaches the resource probe.
        actor = (self.db.query(User).filter(User.id == approver_id)
                 .with_for_update().populate_existing().first())
        if actor is None:
            raise ProfileBearerInvalid("Bearer session unavailable")
        check_profile_bearer(self.db, actor, bearer)
        if not actor.is_superuser and normalize_role_value(actor.role) not in {"admin", "superadmin", "registrar"}:
            raise PriceOverrideApprovalError(403, "Access denied")
        probe = self.db.query(
            DoctorPriceOverride.visit_id, DoctorPriceOverride.doctor_id,
            DoctorPriceOverride.service_id, DoctorPriceOverride.doctor_owner_user_id,
            DoctorPriceOverride.requester_user_id,
        ).filter(DoctorPriceOverride.id == override_id).first()
        if probe is None:
            raise PriceOverrideApprovalError(404, "Изменение цены не найдено")
        user_ids = {approver_id}
        if action == "approve" and probe.doctor_owner_user_id is not None:
            user_ids.add(probe.doctor_owner_user_id)
        if action == "approve" and probe.requester_user_id is not None:
            user_ids.add(probe.requester_user_id)
        # The actor is already locked; NOWAIT on the remaining users avoids
        # waiting in a different order when two reviews share requesters.
        users = (self.db.query(User).filter(User.id.in_(sorted(user_ids)))
                 .order_by(User.id).with_for_update(nowait=True).populate_existing().all())
        users_by_id = {user.id: user for user in users}
        actor = users_by_id.get(approver_id)
        if actor is None:
            raise ProfileBearerInvalid("Bearer session unavailable")
        check_profile_bearer(self.db, actor, bearer)
        doctor = None
        if action == "approve" and probe.doctor_id is not None:
            doctor = (self.db.query(Doctor).filter(Doctor.id == probe.doctor_id)
                      .with_for_update(nowait=True).populate_existing().first())
        patient = group = None
        visit = None
        if action == "approve":
            patient_id = self.db.query(Visit.patient_id).filter(Visit.id == probe.visit_id).scalar()
            if patient_id is None or not lock_patient_subject(self.db, patient_id):
                raise PriceOverrideApprovalError(409, "Контекст визита требует сверки")
            patient = self.db.query(Patient).filter(Patient.id == patient_id).populate_existing().first()
            group = lock_financial_group(self.db, probe.visit_id)
            visit = next((item for item in group.visits if item.id == probe.visit_id), None)
            if patient is None or patient.is_deleted or visit is None or visit.patient_id != patient_id:
                raise PriceOverrideApprovalError(409, "Контекст визита изменился")
        elif probe.visit_id is not None:
            visit = (self.db.query(Visit).filter(Visit.id == probe.visit_id)
                     .with_for_update().populate_existing().first())
        service = None
        if action == "approve" and probe.service_id is not None:
            service = (self.db.query(Service).filter(Service.id == probe.service_id)
                       .with_for_update(nowait=True).populate_existing().first())
        override_query = (self.db.query(DoctorPriceOverride)
                          .filter(DoctorPriceOverride.id == override_id)
                          .populate_existing())
        if self.db.get_bind().dialect.name == "postgresql":
            # Deleting the target child takes its FK SET NULL lock on this
            # override before the child trigger tries to lock Visit. Do not
            # block here while holding Visit or the two writers deadlock.
            override_query = override_query.with_for_update(nowait=True)
        override = override_query.first()
        if override is None:
            raise PriceOverrideApprovalError(404, "Изменение цены не найдено")
        if (override.visit_id, override.doctor_id, override.service_id,
            override.doctor_owner_user_id, override.requester_user_id) != tuple(probe):
            raise PriceOverrideApprovalError(409, "Запрос изменился; повторите операцию")
        return actor, users_by_id, doctor, visit, service, override, patient, group

    def _check_binding(self, users_by_id, doctor, visit, service, override):
        stale = PriceOverrideApprovalError(409, "Запрос устарел; создайте новый запрос")
        owner = users_by_id.get(override.doctor_owner_user_id)
        requester = users_by_id.get(override.requester_user_id)
        # The broad confirmation epoch is evidence of issuance, but changes
        # when another line changes or a confirmation is reissued. The 0112
        # visit/line generations pin this request without invalidating an
        # unrelated pending request; confirmation must be reissued separately.
        if (override.target_scope != "visit_service" or override.target_visit_service_id is None
            or override.visit_context_epoch is None or override.visit_context_epoch < 1
            or override.visit_price_before is None or requester is None or not requester.is_active
            or override.requester_user_id_snapshot != requester.id
            or type(override.requester_auth_epoch) is not int
            or override.requester_auth_epoch < 0
            or requester.auth_epoch != override.requester_auth_epoch
            or override.requester_type not in {"doctor", "admin"}
            or visit is None or type(override.price_context_generation) is not int
            or str(visit.status or "").strip().lower() in {"closed", "canceled", "cancelled", "expired"}
            or override.price_context_generation < 1
            or visit.price_context_generation != override.price_context_generation
            or service is None or not service.active):
            raise stale
        if override.requester_type == "admin":
            if not staff_authorization_service.has_permission(requester, "users:manage"):
                raise stale
        elif (not is_doctor_role_spelling(requester.role)
              or not service.allow_doctor_price_override
              or override.doctor_owner_user_id != requester.id):
            raise stale
        if override.doctor_id is None:
            if (override.requester_type != "admin" or visit.doctor_id is not None
                or override.doctor_owner_user_id is not None
                or override.doctor_owner_generation is not None
                or override.price_owner_generation is not None
                or override.doctor_user_auth_epoch is not None):
                raise stale
        elif (owner is None or not owner.is_active or doctor is None or not doctor.active
              or doctor.id != override.doctor_id or visit.doctor_id != doctor.id
              or doctor.user_id != owner.id or type(override.doctor_owner_generation) is not int
              or override.doctor_owner_generation < 1
              or doctor.repeat_owner_generation != override.doctor_owner_generation
              or type(override.price_owner_generation) is not int
              or override.price_owner_generation < 1
              or doctor.price_owner_generation != override.price_owner_generation
              or type(override.doctor_user_auth_epoch) is not int
              or override.doctor_user_auth_epoch < 0
              or owner.auth_epoch != override.doctor_user_auth_epoch):
            raise stale
        query = (self.db.query(VisitService)
                 .filter(VisitService.id == override.target_visit_service_id,
                         VisitService.visit_id == visit.id, VisitService.service_id == service.id)
                 .populate_existing())
        if self.db.get_bind().dialect.name == "postgresql":
            # 0102 writers take child -> Visit; NOWAIT prevents ABBA while
            # holding this line stable for the price update.
            query = query.with_for_update(nowait=True)
        target = query.first()
        if target is None:
            raise stale
        if (type(override.price_line_generation) is not int
            or override.price_line_generation < 1
            or target.price_line_generation != override.price_line_generation):
            raise stale
        try:
            if parse_money(target.price) != parse_money(override.visit_price_before):
                raise stale
            parse_money(override.new_price)
        except MoneyInputError:
            raise stale from None
        return target

    def _apply_approval(self, *, actor, bearer, visit, patient, override, group, target) -> dict:
        if visit.status == "confirmation_processing":
            raise PriceOverrideApprovalError(409, "Подтверждение визита выполняется")

        previous = parse_money(target.price)
        price = parse_money(override.new_price)
        new_amounts = dict(group.gross_by_visit)
        new_amounts[visit.id] += (price - previous) * target.qty
        requote_draft_invoice_prices(group, new_amounts)

        approved_at = datetime.now(UTC)
        override.status = APPROVED_STATUS
        override.approved_by = actor.id
        override.approved_at = approved_at
        target.price = price
        # Keep the existing service-keyed JSON projection for legacy readers.
        # Assign a new dictionary so the ORM persists subsequent approvals too.
        updated = dict(visit.doctor_price_override or {})
        updated[str(override.service_id)] = {
            "original_price": float(override.original_price),
            "new_price": float(price),
            "override_id": override.id,
            "approved_at": approved_at.isoformat(),
        }
        visit.doctor_price_override = updated
        if visit.status == "pending_confirmation" and price != previous:
            previous_epoch = visit.confirmation_context_epoch
            self.db.flush()
            self.db.refresh(visit)
            if (visit.confirmation_context_epoch == previous_epoch
                    or visit.confirmation_token is not None or visit.confirmation_expires_at is not None):
                raise InvitationRuntimeUnavailable("Confirmation was not invalidated")
            stage_price_approval_recovery(
                self.db, override=override, actor=actor, bearer=bearer,
                patient=patient, visit=visit,
            )

        return {
            "visit_id": visit.id,
            "visit_service_id": target.id,
            "previous_unit_price": str(previous),
            "unit_price": str(price),
            "currency": target.currency,
        }

    def process(
        self,
        *,
        override_id: int,
        action: str,
        rejection_reason: str | None,
        approver_id: int,
        bearer,
    ) -> DoctorPriceOverride:
        """Decide once and commit the price, quote, audit and recovery together."""
        if action not in ("approve", "reject"):
            raise PriceOverrideApprovalError(400, "Действие должно быть 'approve' или 'reject'")
        try:
            actor, users, doctor, visit, service, override, patient, group = self._lock_request(
                override_id, action, approver_id, bearer,
            )
            if override.status != PENDING_STATUS:
                raise PriceOverrideApprovalError(409, "Изменение цены уже обработано")
            if action == "reject":
                reason = (rejection_reason or "").strip()
                if not reason:
                    raise PriceOverrideApprovalError(400, "При отклонении необходимо указать причину")
                override.status = REJECTED_STATUS
                override.approved_by = actor.id
                override.approved_at = datetime.now(UTC)
                override.rejection_reason = reason
                payload = {"visit_id": override.visit_id}
            else:
                target = self._check_binding(users, doctor, visit, service, override)
                payload = self._apply_approval(
                    actor=actor, bearer=bearer, visit=visit, patient=patient,
                    override=override, group=group, target=target,
                )
            self.db.add(AuditLog(
                action=f"price_override_{override.status}",
                entity_type="doctor_price_override", entity_id=override.id,
                actor_user_id=actor.id, payload=payload,
            ))
            self.db.flush()
            check_bearer_expiry(bearer)
            self.db.commit()
            self.db.refresh(override)
            return override
        except (FinancialFenceError, InvitationContextChanged) as exc:
            self.db.rollback()
            raise PriceOverrideApprovalError(409, str(exc)) from None
        except PatientSubjectLockError as exc:
            self.db.rollback()
            raise PriceOverrideApprovalError(exc.status_code, exc.detail) from None
        except InvitationRuntimeUnavailable:
            self.db.rollback()
            raise PriceOverrideApprovalError(503, "Проверка подтверждения временно недоступна") from None
        except ProfileBearerInvalid:
            self.db.rollback()
            raise PriceOverrideApprovalError(401, "Сессия недействительна") from None
        except DBAPIError as exc:
            self.db.rollback()
            dialect = self.db.get_bind().dialect.name
            sqlite_code = getattr(exc.orig, "sqlite_errorcode", 0) or 0
            pg_code = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
            if ((dialect == "postgresql" and pg_code in {"55P03", "40P01", "40001"})
                or (dialect == "sqlite" and sqlite_code & 255 in (5, 6))):
                raise PriceOverrideApprovalError(409, "Данные изменяются, повторите запрос") from None
            raise
        except Exception:
            self.db.rollback()
            raise
