"""Synthetic tests for the internal, non-authorizing all-free staging seam."""
from __future__ import annotations

import time
from decimal import ROUND_UP, Decimal, Inexact, Rounded, localcontext
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError

from app.models.all_free_request import (
    AllFreeRequest,
    AllFreeRequestEvent,
    AllFreeRequestLine,
)
from app.models.audit import AuditLog
from app.models.billing import Invoice
from app.models.clinic import ClinicSettings
from app.models.encounter import Encounter
from app.models.payment import Payment, PaymentVisit
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.payment_webhook import PaymentTransaction, PaymentWebhook
from app.models.visit import Visit, VisitService
from app.services.all_free_request_service import (
    AllFreeRequestError,
    AllFreeRequestService,
)
from app.services.profile_contact_security import (
    ProfileBearerContext,
    ProfileBearerInvalid,
)


def _bearer(user, *, epoch=None, jti=None, expires=None, patient_id=None):
    return ProfileBearerContext(user.id, user.auth_epoch if epoch is None else epoch, jti or "synthetic-session",
                                int(time.time()) + 600 if expires is None else expires, patient_id)


def _setup(db, patient, service, doctor=None):
    encounter = Encounter(patient_id=patient.id, provenance="new")
    db.add(encounter)
    db.flush()
    visit = Visit(patient_id=patient.id, encounter_id=encounter.id,
                  doctor_id=doctor.id if doctor else None, status="pending_confirmation",
                  confirmation_token=None, confirmed_at=None, confirmation_context_epoch=7)
    db.add(visit)
    db.flush()
    line = VisitService(visit_id=visit.id, service_id=service.id, name="Synthetic",
                        qty=3, price=Decimal("0.07"), currency="UZS")
    db.add(line)
    db.commit()
    return visit, line, encounter


def _stage(db, user, visit):
    return AllFreeRequestService(db).stage_request(visit_id=visit.id, expected_epoch=visit.confirmation_context_epoch,
                                                   bearer=_bearer(user))


def test_stage_exact_pending_policy_snapshot_and_no_phi(db_session, admin_user, test_patient, test_service):
    visit, line, _ = _setup(db_session, test_patient, test_service)
    db_session.add(ClinicSettings(key="all_free_auto_approve", value=True, category="benefits"))
    db_session.commit()
    request = _stage(db_session, admin_user, visit)
    assert request.status == "pending" and request.policy_auto_approve is True
    assert request.baseline_total == Decimal("0.21")
    assert line.price == Decimal("0.07") and visit.status == "pending_confirmation"
    saved_line = db_session.query(AllFreeRequestLine).filter_by(request_id=request.id).one()
    assert (saved_line.quantity, saved_line.unit_price, saved_line.gross_amount) == (3, Decimal("0.07"), Decimal("0.21"))
    event = db_session.query(AllFreeRequestEvent).filter_by(request_id=request.id).one()
    audit = db_session.query(AuditLog).filter_by(action="all_free_requested", entity_id=request.id).one()
    assert event.event_type == "requested"
    assert audit.payload == {"policy_auto_approve": True}
    assert test_patient.phone not in str(audit.payload)
    db_session.rollback()
    assert db_session.query(AllFreeRequest).count() == 0
    assert db_session.query(AllFreeRequestLine).count() == 0
    assert db_session.query(AllFreeRequestEvent).count() == 0
    assert db_session.query(AuditLog).filter_by(action="all_free_requested").count() == 0


def test_superadmin_without_superuser_flag_can_stage_and_review(db_session, admin_user, test_patient, test_service):
    admin_user.role = "SuperAdmin"
    admin_user.is_superuser = False
    db_session.commit()
    visit, _, _ = _setup(db_session, test_patient, test_service)
    request = _stage(db_session, admin_user, visit)
    request_id = request.id
    db_session.commit()
    AllFreeRequestService(db_session).inspect_decision(request_id=request_id, bearer=_bearer(admin_user))
    assert db_session.query(AllFreeRequest).filter_by(id=request_id, status="pending").count() == 1


def test_stage_decimal_is_independent_of_ambient_precision(db_session, admin_user, test_patient, test_service):
    visit, line, _ = _setup(db_session, test_patient, test_service)
    line.price = Decimal("1234.56")
    db_session.commit()
    with localcontext() as context:
        context.prec = 1
        context.rounding = ROUND_UP
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        request = _stage(db_session, admin_user, visit)
    assert request.baseline_total == Decimal("3703.68")


@pytest.mark.parametrize("sqlstate", ["55P03", "40001"])
def test_stage_only_translates_lock_not_available_and_fully_rolls_back(
    db_session, admin_user, test_patient, test_service, monkeypatch, sqlstate,
):
    visit, _, _ = _setup(db_session, test_patient, test_service)
    db_session.add(AuditLog(action="synthetic_before_stage", entity_type="test", entity_id=1,
                            actor_user_id=admin_user.id, payload={}))
    db_session.flush()
    error = Exception("synthetic database error")
    error.sqlstate = sqlstate
    def locked(*_args):
        raise OperationalError("SELECT", {}, error)
    monkeypatch.setattr("app.repositories.all_free_request_repository.AllFreeRequestRepository.lock_lines", locked)
    if sqlstate == "55P03":
        with pytest.raises(AllFreeRequestError) as exc:
            _stage(db_session, admin_user, visit)
        assert exc.value.status_code == 409
        assert db_session.query(AuditLog).filter_by(action="synthetic_before_stage").count() == 0
    else:
        with pytest.raises(OperationalError):
            _stage(db_session, admin_user, visit)
        db_session.rollback()


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_internal_decision_requotes_and_is_rolled_back_atomically(
    db_session, admin_user, test_patient, test_service, action,
):
    visit, line, _ = _setup(db_session, test_patient, test_service)
    request = _stage(db_session, admin_user, visit)
    invoice = PaymentInvoice(patient_id=test_patient.id, total_amount=Decimal("0.21"),
                             currency="UZS", status="pending")
    db_session.add(invoice)
    db_session.flush()
    link = PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=visit.id, visit_amount=Decimal("0.21"))
    db_session.add(link)
    db_session.commit()
    request_id, visit_id, line_id, invoice_id, link_id = request.id, visit.id, line.id, invoice.id, link.id

    result = AllFreeRequestService(db_session)._apply_unpublished_decision(
        request_id=request_id, action=action, bearer=_bearer(admin_user),
    )
    expected = Decimal("0.00") if action == "approve" else Decimal("0.21")
    assert result.status == ("approved" if action == "approve" else "rejected")
    assert db_session.get(AllFreeRequest, request_id).status == result.status
    assert db_session.get(PaymentInvoice, invoice_id).total_amount == expected
    assert db_session.get(PaymentInvoiceVisit, link_id).visit_amount == expected
    assert db_session.get(VisitService, line_id).price * 3 == expected
    assert db_session.query(AllFreeRequestEvent).filter_by(id=result.event_id, event_type=result.status).count() == 1
    db_session.rollback()
    assert db_session.get(AllFreeRequest, request_id).status == "pending"
    assert db_session.get(PaymentInvoice, invoice_id).total_amount == Decimal("0.21")
    assert db_session.get(PaymentInvoiceVisit, link_id).visit_amount == Decimal("0.21")
    assert db_session.get(VisitService, line_id).price == Decimal("0.07")
    assert db_session.get(Visit, visit_id).approval_status != result.status
    assert db_session.query(AllFreeRequestEvent).filter_by(id=result.event_id).count() == 0


@pytest.mark.parametrize("second_action", ["approve", "reject"])
def test_internal_decisions_keep_sibling_pending_and_preserve_its_baseline(
    db_session, admin_user, test_patient, test_service, second_action,
):
    first, _, encounter = _setup(db_session, test_patient, test_service)
    second = Visit(patient_id=test_patient.id, encounter_id=encounter.id,
                   status="pending_confirmation", confirmation_context_epoch=8)
    db_session.add(second)
    db_session.flush()
    db_session.add(VisitService(visit_id=second.id, service_id=test_service.id,
                                name="Synthetic", qty=1, price=Decimal("0.11"), currency="UZS"))
    db_session.commit()
    first_request = _stage(db_session, admin_user, first)
    first_id = first_request.id
    db_session.commit()
    second_request = _stage(db_session, admin_user, second)
    second_id = second_request.id
    invoice = PaymentInvoice(patient_id=test_patient.id, total_amount=Decimal("0.32"),
                             currency="UZS", status="pending")
    db_session.add(invoice)
    db_session.flush()
    db_session.add_all([
        PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=first.id, visit_amount=Decimal("0.21")),
        PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=second.id, visit_amount=Decimal("0.11")),
    ])
    db_session.commit()
    service = AllFreeRequestService(db_session)
    service._apply_unpublished_decision(request_id=first_id, action="approve", bearer=_bearer(admin_user))
    db_session.commit()
    assert db_session.get(AllFreeRequest, second_id).status == "pending"
    assert db_session.get(PaymentInvoice, invoice.id).total_amount == Decimal("0.11")
    from app.services.payment_invariant_service import PaymentInvariantService

    with pytest.raises(HTTPException) as blocked:
        PaymentInvariantService(db_session).preflight_payment_groups([first.id])
    assert blocked.value.status_code == 409
    service._apply_unpublished_decision(request_id=second_id, action=second_action, bearer=_bearer(admin_user))
    assert db_session.get(PaymentInvoice, invoice.id).total_amount == (
        Decimal("0.00") if second_action == "approve" else Decimal("0.11")
    )


def test_internal_decision_audit_failure_cannot_be_committed(
    db_session, admin_user, test_patient, test_service, monkeypatch,
):
    visit, _, _ = _setup(db_session, test_patient, test_service)
    request = _stage(db_session, admin_user, visit)
    db_session.commit()
    request_id, visit_id = request.id, visit.id
    original_flush = db_session.flush

    def fail_audit(*args, **kwargs):
        if any(isinstance(item, AuditLog) and item.action == "all_free_decided" for item in db_session.new):
            raise RuntimeError("synthetic audit failure")
        return original_flush(*args, **kwargs)

    monkeypatch.setattr(db_session, "flush", fail_audit)
    with pytest.raises(RuntimeError, match="audit failure"):
        AllFreeRequestService(db_session)._apply_unpublished_decision(
            request_id=request_id, action="approve", bearer=_bearer(admin_user),
        )
    db_session.commit()
    assert db_session.get(AllFreeRequest, request_id).status == "pending"
    assert db_session.query(VisitService).filter_by(visit_id=visit_id).one().price == Decimal("0.07")
    assert db_session.query(AllFreeRequestEvent).filter_by(request_id=request_id).count() == 1


@pytest.mark.parametrize("policy_enabled", [True, False])
def test_internal_auto_decision_rechecks_current_policy(
    db_session, admin_user, test_patient, test_service, policy_enabled,
):
    db_session.add(ClinicSettings(key="all_free_auto_approve", value=True, category="benefits"))
    db_session.commit()
    visit, _, _ = _setup(db_session, test_patient, test_service)
    request = _stage(db_session, admin_user, visit)
    request_id = request.id
    db_session.commit()
    setting = db_session.query(ClinicSettings).filter_by(key="all_free_auto_approve").one()
    setting.value = policy_enabled
    db_session.commit()
    service = AllFreeRequestService(db_session)
    if policy_enabled:
        result = service._apply_unpublished_decision(request_id=request_id, action="approve",
                                                    decision_kind="policy", bearer=_bearer(admin_user))
        assert result.status == "approved"
        assert db_session.get(AllFreeRequest, request_id).decision_kind == "policy"
    else:
        with pytest.raises(AllFreeRequestError) as exc:
            service._apply_unpublished_decision(request_id=request_id, action="approve",
                                                decision_kind="policy", bearer=_bearer(admin_user))
        assert exc.value.status_code == 403
        assert db_session.get(AllFreeRequest, request_id).status == "pending"


@pytest.mark.parametrize("active", [True, False])
def test_internal_auto_decision_rechecks_assigned_doctor(
    db_session, cardio_user, test_doctor, test_patient, test_service, active,
):
    db_session.add(ClinicSettings(key="all_free_auto_approve", value=True, category="benefits"))
    db_session.commit()
    visit, _, _ = _setup(db_session, test_patient, test_service, test_doctor)
    request = _stage(db_session, cardio_user, visit)
    request_id = request.id
    db_session.commit()
    test_doctor.active = active
    db_session.commit()
    service = AllFreeRequestService(db_session)
    if active:
        result = service._apply_unpublished_decision(request_id=request_id, action="approve",
                                                    decision_kind="policy", bearer=_bearer(cardio_user))
        assert result.status == "approved"
    else:
        with pytest.raises(AllFreeRequestError) as exc:
            service._apply_unpublished_decision(request_id=request_id, action="approve",
                                                decision_kind="policy", bearer=_bearer(cardio_user))
        assert exc.value.status_code == 403
        assert db_session.get(AllFreeRequest, request_id).status == "pending"


def test_audit_failure_rolls_back_all_request_rows(db_session, admin_user, test_patient, test_service, monkeypatch):
    visit, _, _ = _setup(db_session, test_patient, test_service)
    flush = db_session.flush
    def fail_audit(*args, **kwargs):
        if any(isinstance(item, AuditLog) for item in db_session.new):
            raise RuntimeError("synthetic audit failure")
        return flush(*args, **kwargs)
    monkeypatch.setattr(db_session, "flush", fail_audit)
    with pytest.raises(RuntimeError, match="audit"):
        _stage(db_session, admin_user, visit)
    db_session.rollback()
    assert db_session.query(AllFreeRequest).count() == 0
    assert db_session.query(AllFreeRequestLine).count() == 0
    assert db_session.query(AllFreeRequestEvent).count() == 0
    assert db_session.query(AuditLog).filter_by(action="all_free_requested").count() == 0


@pytest.mark.parametrize("invalid", ["epoch", "expired", "patient", "disabled", "jti"])
def test_bad_bearer_never_stages(db_session, admin_user, test_patient, test_service, monkeypatch, invalid):
    visit, _, _ = _setup(db_session, test_patient, test_service)
    bearer = _bearer(admin_user)
    if invalid == "epoch":
        bearer = _bearer(admin_user, epoch=admin_user.auth_epoch + 1)
    elif invalid == "expired":
        bearer = _bearer(admin_user, expires=int(time.time()) - 1)
    elif invalid == "patient":
        bearer = _bearer(admin_user, patient_id=test_patient.id)
    elif invalid == "disabled":
        admin_user.is_active = False
        db_session.commit()
    else:
        from app.services.profile_contact_security import token_blacklist_service
        bearer = _bearer(admin_user, jti="synthetic-revoked")
        monkeypatch.setattr(token_blacklist_service, "is_token_blacklisted", lambda *a, **k: True)
    with pytest.raises(ProfileBearerInvalid):
        AllFreeRequestService(db_session).stage_request(visit_id=visit.id, expected_epoch=visit.confirmation_context_epoch, bearer=bearer)
    assert db_session.query(AllFreeRequest).count() == 0


def test_doctor_can_stage_only_assigned_visit(db_session, cardio_user, test_doctor, test_patient, test_service):
    visit, _, _ = _setup(db_session, test_patient, test_service, test_doctor)
    request = _stage(db_session, cardio_user, visit)
    assert request.status == "pending"
    db_session.rollback()
    test_doctor.user_id = None
    db_session.commit()
    with pytest.raises(AllFreeRequestError) as error:
        _stage(db_session, cardio_user, visit)
    assert error.value.status_code == 403


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_decision_never_grants_or_changes_prices(db_session, admin_user, test_patient, test_service, action):
    visit, line, _ = _setup(db_session, test_patient, test_service)
    request = _stage(db_session, admin_user, visit)
    request_id = request.id
    db_session.commit()
    with pytest.raises(AllFreeRequestError) as error:
        AllFreeRequestService(db_session).decide(request_id=request_id, action=action, bearer=_bearer(admin_user))
    assert error.value.status_code == 409
    db_session.refresh(request)
    assert request.status == "pending" and line.price == Decimal("0.07")
    assert db_session.query(AllFreeRequestEvent).filter_by(request_id=request.id).count() == 1


@pytest.mark.parametrize("request_id", [True, 0, -1, "1"])
def test_decision_rejects_nonpositive_or_nonstrict_request_id(db_session, admin_user, request_id):
    with pytest.raises(AllFreeRequestError) as error:
        AllFreeRequestService(db_session).inspect_decision(request_id=request_id, bearer=_bearer(admin_user))
    assert error.value.status_code == 404


def test_stale_epoch_and_aba_refuse_decision(db_session, admin_user, test_patient, test_service):
    visit, line, _ = _setup(db_session, test_patient, test_service)
    request = _stage(db_session, admin_user, visit)
    db_session.commit()
    line.price = Decimal("0.08")
    visit.confirmation_context_epoch += 1
    db_session.flush()
    line.price = Decimal("0.07")
    visit.confirmation_context_epoch += 1
    db_session.commit()
    with pytest.raises(AllFreeRequestError) as error:
        AllFreeRequestService(db_session).inspect_decision(request_id=request.id, bearer=_bearer(admin_user))
    assert error.value.status_code == 409
    assert request.status == "pending"


@pytest.mark.parametrize("state", ["missing", "legacy", "confirmed", "token"])
def test_unresolved_or_already_confirmed_visit_rejected(db_session, admin_user, test_patient, test_service, state):
    visit, _, encounter = _setup(db_session, test_patient, test_service)
    if state == "missing":
        visit.encounter_id = None
    elif state == "legacy":
        encounter.provenance = "legacy_unresolved"
    elif state == "confirmed":
        visit.status = "confirmed"
    else:
        visit.confirmation_token = "synthetic-token"
    db_session.commit()
    with pytest.raises(AllFreeRequestError) as error:
        _stage(db_session, admin_user, visit)
    assert error.value.status_code == 409
    assert db_session.query(AllFreeRequest).count() == 0


@pytest.mark.parametrize("kind", ["payment", "payment_visit", "invoice", "invoice_link", "webhook", "transaction"])
def test_any_financial_history_blocks_stage(db_session, admin_user, test_patient, test_service, kind):
    visit, _, _ = _setup(db_session, test_patient, test_service)
    if kind == "payment":
        db_session.add(Payment(visit_id=visit.id, amount=Decimal("0.01"), status="failed"))
    elif kind == "payment_visit":
        other = Visit(patient_id=test_patient.id, status="open")
        db_session.add(other)
        db_session.flush()
        payment = Payment(visit_id=other.id, amount=Decimal("0.01"), status="failed")
        db_session.add(payment)
        db_session.flush()
        db_session.add(PaymentVisit(payment_id=payment.id, visit_id=visit.id, amount=Decimal("0.01")))
    elif kind == "invoice":
        db_session.add(Invoice(invoice_number=f"synthetic-{uuid4()}", patient_id=test_patient.id, visit_id=visit.id))
    elif kind == "invoice_link":
        invoice = PaymentInvoice(patient_id=test_patient.id, total_amount=Decimal("0.21"), status="pending")
        db_session.add(invoice)
        db_session.flush()
        db_session.add(PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=visit.id, visit_amount=Decimal("0.21")))
    elif kind == "webhook":
        db_session.add(PaymentWebhook(provider="synthetic", webhook_id=str(uuid4()), transaction_id=str(uuid4()),
                                      amount=1, raw_data={}, visit_id=visit.id))
    else:
        db_session.add(PaymentTransaction(provider="synthetic", transaction_id=str(uuid4()), amount=1, visit_id=visit.id))
    db_session.commit()
    with pytest.raises(AllFreeRequestError) as error:
        _stage(db_session, admin_user, visit)
    assert error.value.status_code == 409
    assert db_session.query(AllFreeRequest).count() == 0


def test_existing_pending_request_and_dirty_uow_fail_closed(db_session, admin_user, test_patient, test_service):
    visit, line, _ = _setup(db_session, test_patient, test_service)
    _stage(db_session, admin_user, visit)
    db_session.commit()
    with pytest.raises(AllFreeRequestError) as error:
        _stage(db_session, admin_user, visit)
    assert error.value.status_code == 409
    line.price = Decimal("0.08")
    with pytest.raises(AllFreeRequestError):
        _stage(db_session, admin_user, visit)
    assert line.price == Decimal("0.08")


@pytest.mark.parametrize("expected_epoch", [True, 0, -1, 8])
def test_stage_rejects_invalid_or_stale_epoch(db_session, admin_user, test_patient, test_service, expected_epoch):
    visit, _, _ = _setup(db_session, test_patient, test_service)
    with pytest.raises(AllFreeRequestError) as error:
        AllFreeRequestService(db_session).stage_request(visit_id=visit.id, expected_epoch=expected_epoch, bearer=_bearer(admin_user))
    assert error.value.status_code == 409
    assert db_session.query(AllFreeRequest).count() == 0


def test_doctor_cannot_inspect_admin_decision(db_session, admin_user, cardio_user, test_doctor, test_patient, test_service):
    visit, _, _ = _setup(db_session, test_patient, test_service, test_doctor)
    request = _stage(db_session, admin_user, visit)
    db_session.commit()
    with pytest.raises(AllFreeRequestError) as error:
        AllFreeRequestService(db_session).inspect_decision(request_id=request.id, bearer=_bearer(cardio_user))
    assert error.value.status_code == 403
    assert request.status == "pending"


def _assert_no_evidence(db):
    assert db.query(AllFreeRequest).count() == 0
    assert db.query(AllFreeRequestLine).count() == 0
    assert db.query(AllFreeRequestEvent).count() == 0
    assert db.query(AuditLog).filter_by(action="all_free_requested").count() == 0


def test_conftest_savepoint_failure_then_caller_commit_has_no_evidence(
    db_session, admin_user, test_patient, test_service, monkeypatch
):
    import app.services.all_free_request_service as module
    visit, _, _ = _setup(db_session, test_patient, test_service)
    def expire_after_flush(_bearer):
        assert db_session.query(AllFreeRequest).count() == 1
        assert db_session.query(AllFreeRequestLine).count() == 1
        assert db_session.query(AllFreeRequestEvent).count() == 1
        assert db_session.query(AuditLog).filter_by(action="all_free_requested").count() == 1
        raise ProfileBearerInvalid("synthetic expiration after flush")
    monkeypatch.setattr(module, "check_bearer_expiry", expire_after_flush)
    with pytest.raises(ProfileBearerInvalid):
        _stage(db_session, admin_user, visit)
    db_session.commit()
    _assert_no_evidence(db_session)


@pytest.fixture
def standalone_sqlite(tmp_path):
    """Independent outer transactions and observer, not conftest's savepoint."""
    import sqlalchemy as sa
    from sqlalchemy.orm import Session

    from app.db.base_class import Base
    from app.models.patient import Patient
    from app.models.service import Service
    from app.models.user import User

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'allfree-uow.sqlite'}")
    @sa.event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user = User(username="synthetic-atomic", hashed_password="!", role="Admin", is_active=True, auth_epoch=0)
        patient = Patient(first_name="Synthetic", last_name="Atomic")
        service = Service(code="synthetic-atomic", name="Synthetic", active=True, price=Decimal("0.07"))
        db.add_all([user, patient, service])
        db.flush()
        visit, _, _ = _setup(db, patient, service)
        ids = {"user": user.id, "visit": visit.id, "epoch": visit.confirmation_context_epoch}
    try:
        yield engine, ids
    finally:
        engine.dispose()


@pytest.mark.parametrize("failure", ["expiry", "audit"])
def test_sqlite_failed_stage_outer_commit_is_atomic(standalone_sqlite, monkeypatch, failure):
    import sqlalchemy as sa
    from sqlalchemy.orm import Session

    import app.services.all_free_request_service as module

    engine, ids = standalone_sqlite
    with Session(engine) as db:
        bearer = ProfileBearerContext(ids["user"], 0, "synthetic-jti", int(time.time()) + 600, None)
        if failure == "expiry":
            def expire_after_flush(_bearer):
                assert db.query(AllFreeRequest).count() == 1
                assert db.query(AllFreeRequestLine).count() == 1
                assert db.query(AllFreeRequestEvent).count() == 1
                assert db.query(AuditLog).filter_by(action="all_free_requested").count() == 1
                raise ProfileBearerInvalid("synthetic expiration after flush")
            monkeypatch.setattr(module, "check_bearer_expiry", expire_after_flush)
        else:
            @sa.event.listens_for(db, "before_flush")
            def fail_audit(session, _context, _instances):
                if any(isinstance(item, AuditLog) for item in session.new):
                    raise RuntimeError("synthetic audit flush failure")
        with pytest.raises(ProfileBearerInvalid if failure == "expiry" else RuntimeError):
            AllFreeRequestService(db).stage_request(visit_id=ids["visit"], expected_epoch=ids["epoch"], bearer=bearer)
        # Deliberately catch the exception and commit the outer transaction.
        db.commit()
    with Session(engine) as observer:
        _assert_no_evidence(observer)


def test_sqlite_successful_stage_then_root_rollback_is_atomic(standalone_sqlite):
    from sqlalchemy.orm import Session
    engine, ids = standalone_sqlite
    with Session(engine) as db:
        bearer = ProfileBearerContext(ids["user"], 0, "synthetic-jti", int(time.time()) + 600, None)
        AllFreeRequestService(db).stage_request(visit_id=ids["visit"], expected_epoch=ids["epoch"], bearer=bearer)
        assert db.query(AllFreeRequest).count() == 1
        db.rollback()
    with Session(engine) as observer:
        _assert_no_evidence(observer)


@pytest.mark.parametrize("jti,expiry", [(None, 9999999999), ("", 9999999999), ("synthetic-jti", None), ("synthetic-jti", True)])
def test_incomplete_bearer_is_rejected(db_session, admin_user, test_patient, test_service, jti, expiry):
    visit, _, _ = _setup(db_session, test_patient, test_service)
    bearer = ProfileBearerContext(admin_user.id, admin_user.auth_epoch, jti, expiry, None)
    with pytest.raises(ProfileBearerInvalid):
        AllFreeRequestService(db_session).stage_request(visit_id=visit.id, expected_epoch=visit.confirmation_context_epoch, bearer=bearer)
    _assert_no_evidence(db_session)


@pytest.mark.parametrize("role", ["Registrar", "Cashier"])
def test_authorized_staff_can_stage_without_grant(db_session, test_patient, test_service, role):
    from app.models.user import User
    visit, _, _ = _setup(db_session, test_patient, test_service)
    actor = User(username=f"synthetic-{role}-{uuid4().hex[:8]}", hashed_password="!", role=role, is_active=True)
    db_session.add(actor)
    db_session.commit()
    request = _stage(db_session, actor, visit)
    assert request.status == "pending"
    assert request.requested_by_user_id == actor.id


def test_other_active_doctor_cannot_stage_assigned_visit(db_session, cardio_user, test_doctor, test_patient, test_service):
    from app.models.user import User
    visit, _, _ = _setup(db_session, test_patient, test_service, test_doctor)
    other = User(username=f"synthetic-other-{uuid4().hex[:8]}", hashed_password="!", role="Doctor", is_active=True)
    db_session.add(other)
    db_session.flush()
    test_doctor.user_id = other.id
    db_session.commit()
    with pytest.raises(AllFreeRequestError) as error:
        _stage(db_session, cardio_user, visit)
    assert error.value.status_code == 403
    _assert_no_evidence(db_session)


@pytest.mark.parametrize("case", ["currency", "overflow"])
def test_mixed_currency_and_aggregate_overflow_are_rejected(db_session, admin_user, test_patient, test_service, case):
    visit, line, _ = _setup(db_session, test_patient, test_service)
    if case == "currency":
        db_session.add(VisitService(visit_id=visit.id, service_id=test_service.id + 100, name="Synthetic",
                                    qty=1, price=Decimal("0.01"), currency="USD"))
    else:
        line.price = Decimal("6000000000.00")
        line.qty = 2
    db_session.commit()
    with pytest.raises(AllFreeRequestError) as error:
        _stage(db_session, admin_user, visit)
    assert error.value.status_code == 409
    _assert_no_evidence(db_session)
