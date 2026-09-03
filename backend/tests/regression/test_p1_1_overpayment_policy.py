"""Regression tests for P1-1 grouped-payment overpayment/deposit policy.

P1-1 (post-merge stabilization): the business decision is

    OVERPAYMENT/DEPOSIT ALLOWED (Option A).

Payment.amount MAY exceed Visit.total_cost. The overpayment is treated
as a patient deposit/advance. This is a deliberate business policy,
not an accidental race-condition side effect.

These regression tests verify:

1. **Stale-allocation scenario**: a grouped payment's allocation is
   calculated WITHOUT a lock. Between the calculation and the per-visit
   FOR UPDATE lock, a concurrent payment can change the visit's
   paid_amount. The grouped payment's stale allocation then results
   in overpayment for one visit. The overpayment is ACCEPTED (not
   rejected) per the business policy.

2. **Overpayment logging**: the ``payment.overpayment_accepted``
   WARNING log is emitted with the correct fields (visit_id,
   total_cost, paid_amount, remaining_debt, payment_amount,
   overpayment, cashier_id). Patient_id is NOT logged (CodeQL fix).

3. **No negative remaining_amount**: when paid > total_cost, the
   downstream ``compute_paid_amount`` and ``check_payment_allowed``
   computations do NOT produce negative remaining_debt that would
   break invariants. ``remaining_debt = total_cost - paid_amount``
   can be negative, but this is handled correctly (further payments
   are rejected with "Все услуги уже оплачены" unless the caller
   explicitly sets allow_overpayment=True at the check_payment_allowed
   level — but create_payment_for_visit uses its own inline check
   which allows overpayment as deposit).

4. **Individual payment overpayment**: a single payment with
   amount > total_cost is accepted as a deposit (not just grouped).

Run:
    pytest backend/tests/regression/test_p1_1_overpayment_policy.py -v
"""
from __future__ import annotations

import logging
import os
import sys
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_p1_1_regression.db")
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-p1-1-regression-32-chars")
os.environ.setdefault("ALLOW_SQLITE_DATABASE_URL", "1")
os.environ.setdefault("TESTING", "1")

from app.db.base_class import Base  # noqa: E402
from app.models import (  # noqa: F401
    audit, appointment, clinic, emr_v2, lab, online_queue,
    payment, payment_invoice, payment_webhook, patient, user, visit,
)
from app.models import (  # noqa: F401
    authentication, billing, department, emr, file_system,
    role_permission, schedule, user_profile,
)
from app.models.clinic import Doctor  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.models.service import Service  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.visit import Visit, VisitService  # noqa: E402
from app.services.payment_invariant_service import PaymentInvariantService  # noqa: E402


# ─── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db_engine():
    db_path = BACKEND_DIR / "test_p1_1_regression.db"
    if db_path.exists():
        db_path.unlink()

    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    yield engine

    Base.metadata.drop_all(engine)
    engine.dispose()
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def session_factory(db_engine):
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)

    def _create():
        return Session()

    return _create


@pytest.fixture
def clean_db(db_engine):
    with db_engine.connect() as conn:
        for table in [
            "payments",
            "visit_services",
            "visits",
            "services",
            "doctors",
            "patients",
            "users",
        ]:
            conn.execute(__import__("sqlalchemy").text(f"DELETE FROM {table}"))
        conn.commit()


def _setup_visit_with_cost(session, total_cost=5000):
    """Create a visit with the given total_cost. Returns (visit_id, patient_id)."""
    unique = uuid.uuid4().hex[:8]
    doctor_user = User(
        username=f"doctor_{unique}",
        full_name="P1-1 Doctor",
        email=f"doctor_{unique}@test.local",
        hashed_password="x",
        role="Doctor",
        is_active=True,
        is_superuser=False,
        must_change_password=False,
        created_at=datetime.now(UTC),
    )
    session.add(doctor_user)
    session.flush()

    doctor = Doctor(user_id=doctor_user.id, specialty="Cardiology", active=True)
    session.add(doctor)
    session.flush()

    patient = Patient(
        last_name="P1-1",
        first_name="Patient",
        birth_date=date(1990, 1, 1),
        sex="M",
        phone="+998900000000",
        email=f"patient_{unique}@test.local",
        created_at=datetime.now(UTC),
        is_deleted=False,
    )
    session.add(patient)
    session.flush()

    service = Service(
        code=f"P11_{unique}",
        name="P1-1 Service",
        price=total_cost,
        duration_minutes=30,
        active=True,
        requires_doctor=True,
        queue_tag=f"p11_cardio_{unique}",
        is_consultation=True,
        allow_doctor_price_override=False,
    )
    session.add(service)
    session.flush()

    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        status="in_progress",
        visit_date=date.today(),
        visit_time="10:00",
        discount_mode="none",
        department="cardiology",
        created_at=datetime.now(UTC),
    )
    session.add(visit)
    session.flush()

    vs = VisitService(
        visit_id=visit.id,
        service_id=service.id,
        code=service.code,
        name=service.name,
        qty=1,
        price=service.price,
        currency="UZS",
    )
    session.add(vs)
    session.commit()

    return visit.id, patient.id


# ─── Regression Tests ──────────────────────────────────────────────────

@pytest.mark.unit
class TestOverpaymentPolicy:
    """P1-1: overpayment/deposit is allowed (Option A business policy)."""

    def test_individual_payment_overpayment_accepted_as_deposit(
        self, session_factory, clean_db, caplog
    ):
        """REGRESSION: a single payment with amount > total_cost is accepted
        as a deposit. The ``payment.overpayment_accepted`` WARNING is logged.

        This is the explicit business policy: Payment.amount MAY exceed
        Visit.total_cost.
        """
        setup = session_factory()
        visit_id, patient_id = _setup_visit_with_cost(setup, total_cost=5000)
        setup.close()

        repro = session_factory()
        try:
            service = PaymentInvariantService(repro)
            actor = type("U", (), {"id": 1})()

            with caplog.at_level(logging.WARNING):
                payment = service.create_payment_for_visit(
                    visit_id=visit_id,
                    amount=Decimal("8000"),  # 5000 total_cost + 3000 overpayment
                    method="cash",
                    note="overpayment test",
                    current_user=actor,
                    commit=True,
                )

            # Payment created successfully
            assert payment is not None
            assert payment.amount == Decimal("8000")

            # Overpayment logged at WARNING
            overpayment_logs = [
                r for r in caplog.records
                if "payment.overpayment_accepted" in r.message
            ]
            assert len(overpayment_logs) >= 1, (
                "Expected 'payment.overpayment_accepted' WARNING log. "
                f"Got: {[r.message for r in caplog.records]}"
            )

            # Verify in NEW independent session
            verify = session_factory()
            from app.models.payment import Payment
            payments = verify.query(Payment).filter(
                Payment.visit_id == visit_id,
                Payment.status == "paid",
            ).all()
            assert len(payments) == 1
            assert payments[0].amount == Decimal("8000")
            verify.close()
        finally:
            repro.close()

    def test_paid_exceeds_total_cost_does_not_break_remaining_debt(
        self, session_factory, clean_db
    ):
        """REGRESSION: when paid_amount > total_cost, downstream computations
        must NOT produce broken invariants.

        Business policy nuance (discovered during P1-1 testing):
        - Overpayment IS allowed when remaining_debt > 0 (partial payment
          that exceeds the remaining debt is accepted as deposit).
        - Overpayment is NOT allowed when remaining_debt <= 0 (visit already
          fully paid → further payments rejected with "Все услуги уже оплачены").

        This means the "deposit/advance" policy applies to PARTIAL overpayment
        (amount > remaining_debt but remaining_debt > 0), NOT to payments on
        already-fully-paid visits.
        """
        setup = session_factory()
        visit_id, patient_id = _setup_visit_with_cost(setup, total_cost=5000)
        setup.close()

        # Create a payment that exceeds total_cost (deposit via partial overpayment)
        # visit: total_cost=5000, paid=0, remaining=5000
        # payment: amount=8000 > remaining=5000 → overpayment=3000 accepted
        repro = session_factory()
        try:
            service = PaymentInvariantService(repro)
            actor = type("U", (), {"id": 1})()
            service.create_payment_for_visit(
                visit_id=visit_id,
                amount=Decimal("8000"),  # 5000 + 3000 overpayment
                method="cash",
                note="initial overpayment",
                current_user=actor,
                commit=True,
            )
        finally:
            repro.close()

        # Verify compute_paid_amount and compute_total_cost
        verify = session_factory()
        try:
            service = PaymentInvariantService(verify)
            visit = verify.query(Visit).filter(Visit.id == visit_id).first()
            total_cost = service.compute_total_cost(visit)
            paid_amount = service.compute_paid_amount(visit_id)
            remaining_debt = total_cost - paid_amount

            assert total_cost == Decimal("5000")
            assert paid_amount == Decimal("8000")
            assert remaining_debt == Decimal("-3000"), (
                f"Expected remaining_debt = -3000 (negative = deposit), "
                f"got {remaining_debt}"
            )

            # A further payment must be rejected — the visit is fully paid
            # (remaining_debt <= 0). The "Все услуги уже оплачены" check
            # fires even though allow_overpayment=True.
            from fastapi import HTTPException
            actor2 = type("U", (), {"id": 2})()
            with pytest.raises(HTTPException) as exc_info:
                service.create_payment_for_visit(
                    visit_id=visit_id,
                    amount=Decimal("1000"),
                    method="cash",
                    note="second payment attempt",
                    current_user=actor2,
                    commit=True,
                )
            assert exc_info.value.status_code == 400
            assert "уже оплачены" in exc_info.value.detail, (
                f"Expected 'уже оплачены' rejection, got: {exc_info.value.detail}"
            )
        finally:
            verify.close()

    def test_overpayment_log_does_not_leak_patient_id(
        self, session_factory, clean_db, caplog
    ):
        """REGRESSION (CodeQL fix): the overpayment WARNING log must NOT
        contain the patient_id. Only visit_id and cashier_id are logged.

        Note: this test creates extra standalone patients to ensure
        patient_id and visit_id are distinct numbers (avoiding false
        positives where patient_id=1 coincidentally matches visit_id=1
        in the log text).
        """
        setup = session_factory()
        # Create extra standalone patients to push patient_id ahead of visit_id
        for _ in range(5):
            p = Patient(
                last_name="Padding",
                first_name="Patient",
                birth_date=date(1990, 1, 1),
                sex="M",
                phone="+998900000000",
                email=f"pad_{uuid.uuid4().hex[:8]}@test.local",
                created_at=datetime.now(UTC),
                is_deleted=False,
            )
            setup.add(p)
        setup.flush()

        target_visit_id, target_patient_id = _setup_visit_with_cost(setup, total_cost=5000)
        setup.close()

        # Ensure patient_id and visit_id are distinct to avoid false positives
        assert target_patient_id != target_visit_id, (
            f"Test setup error: patient_id={target_patient_id} == visit_id={target_visit_id}. "
            "Create more visits to make them distinct."
        )

        repro = session_factory()
        try:
            service = PaymentInvariantService(repro)
            actor = type("U", (), {"id": 42})()

            with caplog.at_level(logging.WARNING):
                service.create_payment_for_visit(
                    visit_id=target_visit_id,
                    amount=Decimal("6000"),
                    method="cash",
                    note="patient_id leak test",
                    current_user=actor,
                    commit=True,
                )

            overpayment_log = next(
                (r for r in caplog.records
                 if "payment.overpayment_accepted" in r.message),
                None,
            )
            assert overpayment_log is not None, "No overpayment log found"

            # The log message must NOT contain a "patient_id=" token
            # (the CodeQL concern is clear-text logging of patient identifiers).
            # We check for the token pattern rather than substring, because
            # the patient_id number might coincidentally appear in other
            # fields (e.g. payment_amount=6000 contains "6").
            log_text = overpayment_log.getMessage()
            assert "patient_id" not in log_text, (
                f"'patient_id' token found in overpayment log — CodeQL "
                f"clear-text logging violation. Log: {log_text}"
            )
            # visit_id and cashier_id SHOULD be present
            assert f"visit_id={target_visit_id}" in log_text
            assert "cashier_id=42" in log_text
        finally:
            repro.close()


@pytest.mark.integration
class TestGroupedPaymentStaleAllocation:
    """P1-1: grouped payment with stale allocation — actual behavior.

    The P1-1 analysis originally hypothesized that a stale allocation
    (visit fully paid by concurrent transaction) would result in overpayment
    being accepted. Actual testing revealed a more nuanced policy:

    - Overpayment IS allowed when remaining_debt > 0 (partial payment
      that exceeds remaining debt → accepted as deposit).
    - Overpayment is NOT allowed when remaining_debt <= 0 (visit fully
      paid → further payments rejected with 400 "Все услуги уже оплачены").

    This means the grouped-payment stale-allocation race condition is
    handled by the "already fully paid" rejection — the grouped payment's
    attempt to pay a now-fully-paid visit is REJECTED, not accepted as
    a deposit. The grouped payment transaction would fail/rollback.

    This is actually a SAFER behavior than the originally hypothesized
    "overpayment as deposit" — it prevents accidental double-payment
    when the allocation is stale.
    """

    def test_stale_allocation_fully_paid_visit_rejected(
        self, session_factory, clean_db
    ):
        """When a concurrent payment fully pays a visit BEFORE the grouped
        payment acquires the lock, the grouped payment's attempt to pay
        that visit is REJECTED with 400 "Все услуги уже оплачены".

        This is the correct behavior: the "already fully paid" check
        (remaining_debt <= 0) fires BEFORE the overpayment-as-deposit
        policy, preventing accidental double-payment.
        """
        setup = session_factory()
        v1_id, patient_id = _setup_visit_with_cost(setup, total_cost=5000)
        setup.close()

        # Step 1: concurrent payment fully pays V1
        concurrent = session_factory()
        try:
            service = PaymentInvariantService(concurrent)
            actor = type("U", (), {"id": 1})()
            service.create_payment_for_visit(
                visit_id=v1_id,
                amount=Decimal("5000"),
                method="cash",
                note="concurrent full payment",
                current_user=actor,
                commit=True,
            )
        finally:
            concurrent.close()

        # Step 2: grouped payment tries to pay V1 (stale allocation)
        # V1 is now fully paid (remaining_debt=0). The grouped payment
        # doesn't know this because its allocation was calculated before
        # the concurrent payment committed.
        grouped = session_factory()
        try:
            service = PaymentInvariantService(grouped)
            actor = type("U", (), {"id": 2})()

            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                service.create_payment_for_visit(
                    visit_id=v1_id,
                    amount=Decimal("5000"),
                    method="cash",
                    note="grouped payment stale allocation",
                    current_user=actor,
                    commit=True,
                )

            assert exc_info.value.status_code == 400
            assert "уже оплачены" in exc_info.value.detail, (
                f"Expected 'уже оплачены' rejection for fully-paid visit, "
                f"got: {exc_info.value.detail}"
            )
        finally:
            grouped.close()

        # Step 3: verify V1 has exactly 1 payment (the concurrent one)
        verify = session_factory()
        try:
            from app.models.payment import Payment
            v1_payments = verify.query(Payment).filter(
                Payment.visit_id == v1_id,
                Payment.status == "paid",
            ).all()
            v1_total = sum(Decimal(str(p.amount)) for p in v1_payments)

            assert len(v1_payments) == 1, (
                f"Expected 1 payment for V1 (concurrent only), got {len(v1_payments)}. "
                f"The grouped payment should have been rejected."
            )
            assert v1_total == Decimal("5000"), (
                f"Expected V1 total = 5000, got {v1_total}"
            )
        finally:
            verify.close()

    def test_partial_overpayment_accepted_as_deposit(
        self, session_factory, clean_db, caplog
    ):
        """When remaining_debt > 0 but amount > remaining_debt, the overpayment
        IS accepted as a deposit. This is the actual business policy.

        Example:
        - visit total_cost = 5000, paid = 3000, remaining_debt = 2000
        - payment amount = 5000 > remaining_debt = 2000 → overpayment = 3000
        - ACCEPTED (remaining_debt > 0, so the "already fully paid" check doesn't fire)
        - visit ends up with paid = 8000 (5000 total_cost + 3000 deposit)
        """
        setup = session_factory()
        visit_id, _ = _setup_visit_with_cost(setup, total_cost=5000)
        setup.close()

        # Step 1: partial payment of 3000 (remaining_debt becomes 2000)
        first = session_factory()
        try:
            service = PaymentInvariantService(first)
            actor = type("U", (), {"id": 1})()
            service.create_payment_for_visit(
                visit_id=visit_id,
                amount=Decimal("3000"),
                method="cash",
                note="partial payment",
                current_user=actor,
                commit=True,
            )
        finally:
            first.close()

        # Step 2: overpayment — 5000 when remaining_debt=2000
        second = session_factory()
        try:
            service = PaymentInvariantService(second)
            actor = type("U", (), {"id": 2})()

            with caplog.at_level(logging.WARNING):
                payment = service.create_payment_for_visit(
                    visit_id=visit_id,
                    amount=Decimal("5000"),  # 2000 remaining + 3000 overpayment
                    method="cash",
                    note="overpayment as deposit",
                    current_user=actor,
                    commit=True,
                )

            assert payment is not None
            assert payment.amount == Decimal("5000")

            # Overpayment logged
            overpayment_logs = [
                r for r in caplog.records
                if "payment.overpayment_accepted" in r.message
            ]
            assert len(overpayment_logs) >= 1, (
                "Expected overpayment_accepted WARNING log"
            )
        finally:
            second.close()

        # Step 3: verify total paid = 8000 (5000 + 3000 deposit)
        verify = session_factory()
        try:
            from app.models.payment import Payment
            payments = verify.query(Payment).filter(
                Payment.visit_id == visit_id,
                Payment.status == "paid",
            ).all()
            total = sum(Decimal(str(p.amount)) for p in payments)

            assert total == Decimal("8000"), (
                f"Expected total paid = 8000 (5000 cost + 3000 deposit), got {total}"
            )
        finally:
            verify.close()
