"""Internal all-free staging and unpublished decision primitives.

The public decision seam remains closed while producers, financial writers,
and invitation recovery are integrated. The private decision primitive mutates
only the caller's transaction; it never commits or dispatches notifications.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, InvalidOperation, localcontext

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.roles import is_doctor_role_spelling, normalize_role_value
from app.models.all_free_request import (
    AllFreeRequest,
    AllFreeRequestEvent,
    AllFreeRequestLine,
)
from app.models.audit import AuditLog
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit
from app.repositories.all_free_request_repository import AllFreeRequestRepository
from app.services.all_free_policy import load_all_free_auto_approve
from app.services.profile_contact_security import (
    ProfileBearerContext,
    ProfileBearerInvalid,
    check_bearer_expiry,
    check_profile_bearer,
)

_MAX_AMOUNT = Decimal("9999999999.99")
_CENT = Decimal("0.01")


class AllFreeRequestError(ValueError):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class InternalAllFreeDecision:
    """Uncommitted result for a later invitation-aware transaction owner."""

    request_id: int
    event_id: int
    visit_id: int
    status: str
    final_visit_epoch: int


def _amount(value: object) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise AllFreeRequestError(409, "Цена заявки требует проверки")
    try:
        with localcontext(Context(prec=40, rounding=ROUND_HALF_EVEN)):
            invalid = value < 0 or value > _MAX_AMOUNT or value != value.quantize(_CENT)
    except InvalidOperation:
        invalid = True
    if invalid:
        raise AllFreeRequestError(409, "Цена заявки требует проверки")
    return value


class AllFreeRequestService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AllFreeRequestRepository(db)

    def _require_flushed_session(self) -> None:
        # populate_existing must never discard a caller's pending mutations.
        # The owning transaction must flush its locked preparation first.
        if self.db.new or self.db.dirty or self.db.deleted:
            raise AllFreeRequestError(409, "Сначала сохраните изменения визита в транзакции")

    def _lock_actor(self, bearer: ProfileBearerContext) -> User:
        if (not isinstance(bearer, ProfileBearerContext)
                or type(bearer.user_id) is not int or bearer.user_id <= 0
                or type(bearer.auth_epoch) is not int or bearer.auth_epoch < 0
                or not isinstance(bearer.jti, str) or not bearer.jti
                or type(bearer.expires_at) is not int or bearer.expires_at <= 0
                or bearer.patient_id is not None):
            raise ProfileBearerInvalid("Bearer session unavailable")
        actor = (self.db.query(User).filter(User.id == bearer.user_id)
                 .with_for_update().populate_existing().first())
        if actor is None:
            raise ProfileBearerInvalid("Bearer session unavailable")
        check_profile_bearer(self.db, actor, bearer)
        return actor

    def _lock_stage_visit(self, actor: User, visit_id: int) -> Visit:
        role = normalize_role_value(actor.role)
        doctor_role = is_doctor_role_spelling(role) and not actor.is_superuser
        if not actor.is_superuser and role not in {"admin", "superadmin", "registrar", "cashier"} and not doctor_role:
            raise AllFreeRequestError(403, "Доступ запрещён")
        doctor_hint = self.db.query(Visit.doctor_id).filter(Visit.id == visit_id).first()
        if doctor_hint is None:
            raise AllFreeRequestError(404, "Визит не найден")
        doctor = None
        if doctor_role and doctor_hint[0] is not None:
            doctor = (self.db.query(Doctor).filter(Doctor.id == doctor_hint[0])
                      .with_for_update().populate_existing().first())
        visit = self.repo.lock_visit(visit_id)
        if visit is None:
            raise AllFreeRequestError(404, "Визит не найден")
        if doctor_role and (
            doctor is None or visit.doctor_id != doctor_hint[0]
            or doctor.user_id != actor.id or doctor.active is not True
        ):
            raise AllFreeRequestError(403, "Доступ запрещён")
        return visit

    def _snapshot(
        self, visit: Visit, expected_epoch: int, *, check_financial_history: bool = True,
    ) -> tuple[object, list[tuple[object, Decimal, Decimal]], Decimal]:
        if type(expected_epoch) is not int or expected_epoch <= 0 or visit.confirmation_context_epoch != expected_epoch:
            raise AllFreeRequestError(409, "Контекст визита изменился")
        if (visit.status != "pending_confirmation" or visit.confirmed_at is not None
                or visit.confirmation_token is not None or visit.encounter_id is None):
            raise AllFreeRequestError(409, "Визит недоступен для новой заявки")
        encounter = self.repo.lock_encounter(visit.encounter_id)
        if (encounter is None or encounter.patient_id != visit.patient_id
                or encounter.provenance != "new"):
            raise AllFreeRequestError(409, "Требуется сверка обращения")
        try:
            lines = self.repo.lock_lines(visit.id)
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) == "55P03" or getattr(exc.orig, "pgcode", None) == "55P03":
                self.db.rollback()
                raise AllFreeRequestError(409, "Состав услуг изменяется; повторите запрос") from None
            raise
        if not lines:
            raise AllFreeRequestError(409, "Визит не содержит услуг")
        snapshot = []
        total = Decimal("0.00")
        currency = None
        for line in lines:
            if (type(line.id) is not int or line.id <= 0
                    or type(line.service_id) is not int or line.service_id <= 0
                    or type(line.qty) is not int or not 0 < line.qty <= 2147483647
                    or not isinstance(line.currency, str) or not line.currency.strip()
                    or len(line.currency) > 8):
                raise AllFreeRequestError(409, "Состав заявки требует проверки")
            if currency is None:
                currency = line.currency
            elif currency != line.currency:
                raise AllFreeRequestError(409, "В заявке смешаны валюты")
            unit = _amount(line.price)
            with localcontext(Context(prec=40, rounding=ROUND_HALF_EVEN)):
                gross = unit * line.qty
                total += gross
            if gross > _MAX_AMOUNT or total > _MAX_AMOUNT:
                raise AllFreeRequestError(409, "Сумма заявки превышает допустимую")
            snapshot.append((line, unit, gross))
        # The cart already proves the full financial group. The original
        # internal callers retain their conservative per-visit history check.
        if check_financial_history and self.repo.has_financial_history(visit.id):
            raise AllFreeRequestError(409, "Финансовые операции требуют сверки")
        return encounter, snapshot, total

    def stage_request(
        self, *, visit_id: int, expected_epoch: int, bearer: ProfileBearerContext,
        require_financial_group: bool = False,
    ) -> AllFreeRequest:
        if type(visit_id) is not int or visit_id <= 0:
            raise AllFreeRequestError(404, "Визит не найден")
        actor, policy_auto = self.lock_staging_inputs(bearer)
        if require_financial_group:
            from app.services.encounter_financial_fence import lock_financial_group

            # The cart already holds the Patient lock. Acquire the sorted
            # group locks before taking any individual visit/service locks.
            group = lock_financial_group(
                self.db, visit_id, allow_sibling_pending_for_staging=True,
            )
            if group.invoices:
                raise AllFreeRequestError(409, "Финансовые операции требуют сверки")
        visit = self._lock_stage_visit(actor, visit_id)
        if self.repo.has_active_request(visit.id):
            raise AllFreeRequestError(409, "Для визита уже существует заявка")
        encounter, snapshot, total = self._snapshot(
            visit, expected_epoch, check_financial_history=not require_financial_group,
        )
        # The root policy lock is already held (and SQLite has acquired its
        # write reservation) before this savepoint. Even if a caller catches a
        # post-flush exception and commits its outer transaction, no partial
        # request, lines or audit can escape the failed operation.
        with self.db.begin_nested():
            request = AllFreeRequest(
                visit_id=visit.id, patient_id=visit.patient_id, encounter_id=visit.encounter_id,
                visit_id_snapshot=visit.id, patient_id_snapshot=visit.patient_id,
                encounter_id_snapshot=visit.encounter_id, visit_context_epoch=expected_epoch,
                encounter_generation=encounter.generation, baseline_total=total, status="pending",
                requested_by_user_id=actor.id, requested_by_user_id_snapshot=actor.id,
                requested_by_role_snapshot=normalize_role_value(actor.role), policy_auto_approve=policy_auto,
            )
            self.db.add(request)
            self.db.flush()
            for line, unit, gross in snapshot:
                self.db.add(AllFreeRequestLine(
                    request_id=request.id, visit_id_snapshot=visit.id, visit_service_id=line.id,
                    visit_service_id_snapshot=line.id, service_id_snapshot=line.service_id,
                    quantity=line.qty, unit_price=unit, gross_amount=gross, currency=line.currency,
                ))
            self.db.add(AllFreeRequestEvent(request_id=request.id, event_type="requested",
                                           actor_user_id=actor.id, actor_user_id_snapshot=actor.id,
                                           actor_role_snapshot=normalize_role_value(actor.role)))
            self.db.add(AuditLog(action="all_free_requested", entity_type="all_free_request",
                                 entity_id=request.id, actor_user_id=actor.id,
                                 payload={"policy_auto_approve": policy_auto}))
            self.db.flush()
            check_bearer_expiry(bearer)
            return request

    def lock_staging_inputs(self, bearer: ProfileBearerContext) -> tuple[User, bool]:
        """Acquire policy and actor locks before a producer prepares new visits."""
        self._require_flushed_session()
        policy_auto = load_all_free_auto_approve(self.db)
        return self._lock_actor(bearer), policy_auto

    def inspect_decision(self, *, request_id: int, bearer: ProfileBearerContext) -> None:
        """Validate the current evidence; never mutate it or grant a decision."""
        if type(request_id) is not int or request_id <= 0:
            raise AllFreeRequestError(404, "Заявка не найдена")
        self._require_flushed_session()
        load_all_free_auto_approve(self.db)
        actor = self._lock_actor(bearer)
        if not actor.is_superuser and normalize_role_value(actor.role) not in {"admin", "superadmin"}:
            raise AllFreeRequestError(403, "Доступ запрещён")
        hint = self.db.query(AllFreeRequest.visit_id).filter(AllFreeRequest.id == request_id).first()
        if hint is None or hint[0] is None:
            raise AllFreeRequestError(409, "Заявка требует сверки")
        visit = self.repo.lock_visit(hint[0])
        if visit is None:
            raise AllFreeRequestError(409, "Заявка требует сверки")
        encounter, lines, total = self._snapshot(visit, visit.confirmation_context_epoch)
        request = self.repo.lock_request(request_id)
        if (request is None or request.status != "pending" or request.visit_id != visit.id
                or request.patient_id != visit.patient_id or request.encounter_id != visit.encounter_id
                or request.visit_context_epoch != visit.confirmation_context_epoch
                or request.encounter_generation != encounter.generation or request.baseline_total != total):
            raise AllFreeRequestError(409, "Контекст заявки изменился")
        stored = self.repo.request_lines(request.id)
        actual = [(line.id, line.service_id, line.qty, unit, gross, line.currency) for line, unit, gross in lines]
        expected = [(line.visit_service_id, line.service_id_snapshot, line.quantity, line.unit_price,
                     line.gross_amount, line.currency) for line in stored]
        if actual != expected:
            raise AllFreeRequestError(409, "Состав заявки изменился")
        check_bearer_expiry(bearer)

    def decide(self, *, request_id: int, action: str, bearer: ProfileBearerContext) -> None:
        if not isinstance(action, str) or action not in {"approve", "reject"}:
            raise AllFreeRequestError(422, "Недопустимое решение")
        self.inspect_decision(request_id=request_id, bearer=bearer)
        raise AllFreeRequestError(409, "Решение недоступно до завершения финансовой сверки")

    def _apply_unpublished_decision(
        self, *, request_id: int, action: str, bearer: ProfileBearerContext,
        decision_kind: str = "admin",
    ) -> InternalAllFreeDecision:
        """Apply a locked decision; not an HTTP or invitation workflow.

        Until an invitation obligation and all payment/confirmation writers
        are integrated, callers must not publish this as a decision endpoint.
        The caller owns the outer transaction, final bearer check and commit.
        """
        from app.services.all_free_guard import require_all_free_decision_capability
        from app.services.encounter_benefit_net import benefit_visit_quote
        from app.services.encounter_financial_fence import (
            lock_financial_group,
            requote_draft_invoices,
        )
        from app.services.patient_subject_lock import (
            PatientSubjectLockError,
            lock_patient_subject,
            require_patient_subject_visibility,
        )

        if type(request_id) is not int or request_id <= 0:
            raise AllFreeRequestError(404, "Заявка не найдена")
        if not isinstance(action, str) or action not in {"approve", "reject"}:
            raise AllFreeRequestError(422, "Недопустимое решение")
        if (not isinstance(decision_kind, str) or decision_kind not in {"admin", "policy"}
                or (decision_kind == "policy" and action != "approve")):
            raise AllFreeRequestError(422, "Недопустимое решение")
        self._require_flushed_session()
        try:
            # The same transaction must retain the trusted schema and auth
            # visibility proof before the first User/JTI lookup and through
            # the later subject and financial locks.
            require_patient_subject_visibility(self.db)
        except PatientSubjectLockError as exc:
            raise AllFreeRequestError(exc.status_code, exc.detail) from exc
        policy_auto = load_all_free_auto_approve(self.db)
        actor = self._lock_actor(bearer)
        role = normalize_role_value(actor.role)
        if (decision_kind == "admin" and not actor.is_superuser
                and role not in {"admin", "superadmin"}):
            raise AllFreeRequestError(403, "Доступ запрещён")
        hint = (self.db.query(AllFreeRequest.visit_id, AllFreeRequest.patient_id)
                .filter(AllFreeRequest.id == request_id).first())
        if hint is None or hint.visit_id is None or hint.patient_id is None:
            raise AllFreeRequestError(409, "Заявка требует сверки")
        doctor_hint = None
        if decision_kind == "policy":
            doctor_role = is_doctor_role_spelling(role) and not actor.is_superuser
            if not policy_auto or (not actor.is_superuser and role not in {
                "admin", "superadmin", "registrar", "cashier"
            } and not doctor_role):
                raise AllFreeRequestError(403, "Автоматическое решение недоступно")
            if doctor_role:
                doctor_hint = self.db.query(Visit.doctor_id).filter(Visit.id == hint.visit_id).scalar()
                doctor = (self.db.query(Doctor).filter(Doctor.id == doctor_hint)
                          .with_for_update().populate_existing().first())
                if doctor is None or doctor.user_id != actor.id or doctor.active is not True:
                    raise AllFreeRequestError(403, "Автоматическое решение недоступно")
        try:
            locked = lock_patient_subject(self.db, hint.patient_id)
        except PatientSubjectLockError as exc:
            raise AllFreeRequestError(exc.status_code, exc.detail) from exc
        patient = (self.db.query(Patient).filter(Patient.id == hint.patient_id)
                   .populate_existing().first()) if locked else None
        if patient is None or patient.is_deleted:
            raise AllFreeRequestError(409, "Заявка требует сверки")
        try:
            with self.db.begin_nested():
                group = lock_financial_group(self.db, hint.visit_id, allow_all_free_request_id=request_id)
                private = require_all_free_decision_capability(self.db, hint.visit_id)
                request = next((item for item in group.pending_requests if item.id == request_id), None)
                visit = next((item for item in group.visits if item.id == hint.visit_id), None)
                if (request is None or visit is None or request.patient_id != patient.id
                        or visit.patient_id != patient.id or request.encounter_id != group.encounter.id
                        or request.visit_context_epoch != visit.confirmation_context_epoch
                        or request.encounter_generation != group.encounter.generation
                        or request.baseline_total != group.gross_by_visit[visit.id]
                        or visit.status != "pending_confirmation" or visit.confirmed_at is not None
                        or visit.confirmation_token is not None
                        or (doctor_hint is not None and visit.doctor_id != doctor_hint)
                        or (decision_kind == "policy" and (
                            request.policy_auto_approve is not True
                            or request.requested_by_user_id != actor.id
                            or request.requested_by_user_id_snapshot != actor.id))):
                    raise AllFreeRequestError(409, "Контекст заявки изменился")
                # Until versioned reapproval exists, changing a group with an
                # applied benefit must not silently discard that decision.
                if benefit_visit_quote(self.db, visit.id) is not None:
                    raise AllFreeRequestError(409, "Требуется повторное решение по льготе")
                lines = self.repo.lock_lines(visit.id)
                stored = self.repo.request_lines(request.id)
                with localcontext(Context(prec=40, rounding=ROUND_HALF_EVEN)):
                    actual = [(line.id, line.service_id, line.qty, _amount(line.price),
                               _amount(line.price) * line.qty, line.currency) for line in lines]
                expected = [(line.visit_service_id, line.service_id_snapshot, line.quantity,
                             line.unit_price, line.gross_amount, line.currency) for line in stored]
                if not lines or actual != expected:
                    raise AllFreeRequestError(409, "Состав заявки изменился")
                old_epoch = request.visit_context_epoch
                encounter_generation = request.encounter_generation
                status = "approved" if action == "approve" else "rejected"
                if action == "approve":
                    net = dict(group.gross_by_visit)
                    net[visit.id] = Decimal("0.00")
                    requote_draft_invoices(group, net)
                    for line in lines:
                        line.price = Decimal("0.00")
                visit.approval_status = status
                self.db.flush()
                self.db.refresh(visit)
                final_epoch = visit.confirmation_context_epoch
                if private is None:
                    request.status = status
                    request.decision_kind = decision_kind
                    request.decision_context_epoch = final_epoch
                    request.decided_by_user_id = actor.id
                    request.decided_by_user_id_snapshot = actor.id
                    request.decided_by_role_snapshot = role
                    request.decided_at = datetime.now(UTC)
                    event = AllFreeRequestEvent(request_id=request.id, event_type=status,
                                                actor_user_id=actor.id, actor_user_id_snapshot=actor.id,
                                                actor_role_snapshot=role)
                    self.db.add(event)
                    self.db.flush()
                    event_id = event.id
                else:
                    event_id = self.db.execute(text(f"""
                        SELECT {private}.decide_all_free(
                          :request_id, :action, :decision_kind, :actor_id, :auth_epoch,
                          :visit_id, :patient_id, :encounter_id, :old_epoch,
                          :encounter_generation, :final_epoch)
                    """), {"request_id": request_id, "action": action, "decision_kind": decision_kind,
                            "actor_id": actor.id,
                            "auth_epoch": actor.auth_epoch, "visit_id": visit.id,
                            "patient_id": patient.id, "encounter_id": group.encounter.id,
                            "old_epoch": old_epoch, "encounter_generation": encounter_generation,
                            "final_epoch": final_epoch}).scalar_one()
                    self.db.expire(request)
                self.db.add(AuditLog(action="all_free_decided", entity_type="all_free_request",
                                     entity_id=request_id, actor_user_id=actor.id,
                                     payload={"decision": status, "kind": decision_kind, "event_id": event_id}))
                self.db.flush()
                check_bearer_expiry(bearer)
                return InternalAllFreeDecision(request_id, event_id, visit.id, status, final_epoch)
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) == "55P03" or getattr(exc.orig, "pgcode", None) == "55P03":
                self.db.rollback()
                raise AllFreeRequestError(409, "Состав услуг изменяется; повторите запрос") from None
            raise
