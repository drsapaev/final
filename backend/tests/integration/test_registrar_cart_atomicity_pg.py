"""
Fix C — registrar cart atomicity & idempotency integration tests.

These tests run against a DISPOSABLE real PostgreSQL instance (pgserver
embedded binaries). SQLite cannot prove cross-statement transaction
semantics, so the cart-atomicity guarantee is validated here:

- a multi-visit cart commits visits + invoice + invoice/visit links + queue
  entries in ONE transaction;
- a failure at ANY stage (second visit / invoice / queue assignment) leaves
  NO partial cart records behind;
- a retried request with the same Idempotency-Key does not create a second
  cart (lost-response protection, sequential and concurrent single-flight);
- a new Idempotency-Key still allows a brand-new registration.
"""
from __future__ import annotations

import asyncio
import os
import secrets

import pytest
import pytest_asyncio
import sqlalchemy as sa
from fastapi.testclient import TestClient

pytest.importorskip("pgserver", reason="pgserver (disposable PostgreSQL) not installed")

# ============================================================
# Disposable PostgreSQL fixtures (session-scoped server)
# ============================================================

os.environ.setdefault("TESTING", "1")
os.environ.setdefault("ENV", "dev")


@pytest.fixture(scope="module")
def pg_database(tmp_path_factory):
    import pgserver

    data_dir = str(tmp_path_factory.mktemp("pgdata-cart"))
    server = pgserver.get_server(data_dir)
    dbname = f"cart_atomicity_{secrets.token_hex(6)}"
    server.psql(f"CREATE DATABASE {dbname}")
    uri = server.get_uri(dbname)
    yield uri
    server.cleanup()


@pytest.fixture(scope="module")
def pg_engine(pg_database):
    from app.db import base  # noqa: F401 - registers all models
    from app.db.base_class import Base

    engine = sa.create_engine(pg_database, future=True)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def pg_session_factory(pg_engine):
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=pg_engine, autocommit=False, autoflush=False, future=True)


@pytest.fixture(scope="module")
def pg_client(pg_engine, pg_session_factory):
    """TestClient wired to the disposable PostgreSQL via get_db override."""
    from app.api.deps import get_db
    from app.main import app
    from sqlalchemy.orm import Session

    def _override_get_db():
        db = pg_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="module")
def pg_registrar(pg_session_factory):
    from app.core.security import get_password_hash
    from app.models.user import User

    db: Session = pg_session_factory()
    existing = db.query(User).filter(User.username == "cart_atomicity_registrar").first()
    if existing:
        db.close()
        return existing
    user = User(
        username="cart_atomicity_registrar",
        email="cart-atomicity@test.local",
        full_name="Cart Atomicity Registrar",
        hashed_password=get_password_hash("registrar123"),
        role="Registrar",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


@pytest.fixture(scope="module")
def pg_auth_headers(pg_client, pg_registrar):
    response = pg_client.post(
        "/api/v1/authentication/login",
        json={"username": pg_registrar.username, "password": "registrar123"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def pg_patient(pg_session_factory):
    """Fresh patient per test so DB-state assertions are isolated."""
    import secrets as _secrets
    from app.models.patient import Patient

    db: Session = pg_session_factory()
    patient = Patient(
        first_name="Атомарный",
        last_name=f"Пациент-{_secrets.token_hex(4)}",
        phone=f"+99890{_secrets.randbelow(10**8):08d}",
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    patient_id = patient.id
    db.close()
    return patient_id


@pytest.fixture(scope="module")
def pg_service(pg_session_factory):
    from app.models.service import Service

    db: Session = pg_session_factory()
    service = Service(
        name="Атомарная консультация",
        price=100000,
        service_code=f"K{secrets.randbelow(900000) + 100000}",
        is_consultation=True,
        requires_doctor=False,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    service_id = service.id
    db.close()
    return service_id


def _build_cart_payload(patient_id, service_id, visits=2) -> dict:
    from datetime import date

    return {
        "patient_id": patient_id,
        "visits": [
            {
                "doctor_id": None,
                "services": [{"service_id": service_id, "quantity": 1}],
                "visit_date": date.today().isoformat(),
                "visit_time": None,
                "department": "cardiology",
                "notes": None,
            }
            for _ in range(visits)
        ],
        "discount_mode": "none",
        "payment_method": "cash",
        "all_free": False,
        "notes": None,
    }


def _count(pg_session_factory, model, **filters) -> int:
    from sqlalchemy.orm import Session

    db: Session = pg_session_factory()
    try:
        query = db.query(model)
        for column, value in filters.items():
            query = query.filter(getattr(model, column) == value)
        return query.count()
    finally:
        db.close()


# ============================================================
# Atomicity
# ============================================================

def test_successful_multi_visit_cart_commits_everything(
    pg_client, pg_auth_headers, pg_patient, pg_service, pg_session_factory
):
    from app.models.payment_invoice import PaymentInvoice
    from app.models.visit import Visit

    payload = _build_cart_payload(pg_patient, pg_service, visits=2)
    response = pg_client.post("/api/v1/registrar/cart", json=payload, headers=pg_auth_headers)
    assert response.status_code == 200, response.text

    assert _count(pg_session_factory, Visit, patient_id=pg_patient) == 2
    assert _count(pg_session_factory, PaymentInvoice, patient_id=pg_patient) == 1


def test_error_on_second_visit_leaves_no_partial_cart(
    pg_client, pg_auth_headers, pg_patient, pg_service, pg_session_factory, monkeypatch
):
    from app import crud
    from app.models.payment_invoice import PaymentInvoice
    from app.models.visit import Visit
    from app.crud.visit import create_visit as real_create_visit

    call_counter = {"n": 0}

    def flaky_create_visit(*args, **kwargs):
        call_counter["n"] += 1
        if call_counter["n"] >= 2:
            raise RuntimeError("injected failure on the second visit")
        return real_create_visit(*args, **kwargs)

    monkeypatch.setattr(crud.visit, "create_visit", flaky_create_visit)

    payload = _build_cart_payload(pg_patient, pg_service, visits=2)
    response = pg_client.post(
        "/api/v1/registrar/cart", json=payload, headers=pg_auth_headers
    )
    assert response.status_code >= 400

    # Atomicity: the first visit must NOT survive without the rest of the cart.
    assert _count(pg_session_factory, Visit, patient_id=pg_patient) == 0
    assert _count(pg_session_factory, PaymentInvoice, patient_id=pg_patient) == 0


def test_queue_failure_rolls_back_visits_and_invoice(
    pg_client, pg_auth_headers, pg_patient, pg_service, pg_session_factory, monkeypatch
):
    from app.api.v1.endpoints.registrar_wizard import _cart
    from app.models.payment_invoice import PaymentInvoice
    from app.models.visit import Visit

    def broken_assign(self, *args, **kwargs):
        raise RuntimeError("injected queue assignment failure")

    monkeypatch.setattr(
        _cart.RegistrarWizardQueueAssignmentService,
        "assign_same_day_queue_numbers",
        broken_assign,
    )

    payload = _build_cart_payload(pg_patient, pg_service, visits=1)
    response = pg_client.post("/api/v1/registrar/cart", json=payload, headers=pg_auth_headers)
    assert response.status_code >= 400

    assert _count(pg_session_factory, Visit, patient_id=pg_patient) == 0
    assert _count(pg_session_factory, PaymentInvoice, patient_id=pg_patient) == 0


def test_invoice_failure_rolls_back_visits(
    pg_client, pg_auth_headers, pg_patient, pg_service, pg_session_factory, monkeypatch
):
    from app.models.visit import Visit

    import app.api.v1.endpoints.registrar_wizard._cart as cart_module

    real_payment_invoice = cart_module.PaymentInvoice

    class BrokenPaymentInvoice(real_payment_invoice):
        def __init__(self, *args, **kwargs):
            raise RuntimeError("injected invoice creation failure")

    monkeypatch.setattr(cart_module, "PaymentInvoice", BrokenPaymentInvoice)

    payload = _build_cart_payload(pg_patient, pg_service, visits=1)
    response = pg_client.post("/api/v1/registrar/cart", json=payload, headers=pg_auth_headers)
    assert response.status_code >= 400

    assert _count(pg_session_factory, Visit, patient_id=pg_patient) == 0
    monkeypatch.setattr(cart_module, "PaymentInvoice", real_payment_invoice)


# ============================================================
# Idempotency (retry protection)
# ============================================================

def _invoice_count_for_patient(pg_session_factory, pg_patient) -> int:
    from app.models.payment_invoice import PaymentInvoice

    return _count(pg_session_factory, PaymentInvoice, patient_id=pg_patient)


def test_retry_with_same_key_creates_single_cart(
    pg_client, pg_auth_headers, pg_patient, pg_service, pg_session_factory
):
    before = _invoice_count_for_patient(pg_session_factory, pg_patient)
    payload = _build_cart_payload(pg_patient, pg_service, visits=1)
    headers = {**pg_auth_headers, "Idempotency-Key": "atomicity-key-sequential-1"}

    first = pg_client.post("/api/v1/registrar/cart", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    second = pg_client.post("/api/v1/registrar/cart", json=payload, headers=headers)
    assert second.status_code == 200

    assert first.json() == second.json()
    after = _invoice_count_for_patient(pg_session_factory, pg_patient)
    assert after == before + 1  # exactly one cart despite two requests


def test_new_key_allows_new_registration(
    pg_client, pg_auth_headers, pg_patient, pg_service, pg_session_factory
):
    before = _invoice_count_for_patient(pg_session_factory, pg_patient)
    payload = _build_cart_payload(pg_patient, pg_service, visits=1)

    first = pg_client.post(
        "/api/v1/registrar/cart",
        json=payload,
        headers={**pg_auth_headers, "Idempotency-Key": "atomicity-key-new-1"},
    )
    assert first.status_code == 200
    second = pg_client.post(
        "/api/v1/registrar/cart",
        json=payload,
        headers={**pg_auth_headers, "Idempotency-Key": "atomicity-key-new-2"},
    )
    assert second.status_code == 200

    after = _invoice_count_for_patient(pg_session_factory, pg_patient)
    assert after == before + 2  # a new self-contained registration stays possible


def test_parallel_same_key_creates_single_cart(
    pg_client, pg_auth_headers, pg_patient, pg_service, pg_session_factory
):
    """Concurrent duplicate keys share one execution (single-flight)."""
    import httpx
    from app.main import app

    before = _invoice_count_for_patient(pg_session_factory, pg_patient)
    payload = _build_cart_payload(pg_patient, pg_service, visits=1)
    headers = {**pg_auth_headers, "Idempotency-Key": "atomicity-key-parallel-1"}

    async def _parallel_requests():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            return await asyncio.gather(
                ac.post("/api/v1/registrar/cart", json=payload, headers=headers),
                ac.post("/api/v1/registrar/cart", json=payload, headers=headers),
                ac.post("/api/v1/registrar/cart", json=payload, headers=headers),
            )

    from app.api.deps import get_db

    # The dependency override installed by pg_client is reused by the
    # ASGI transport (same app instance).

    responses = asyncio.run(_parallel_requests())
    assert all(r.status_code == 200 for r in responses), [r.status_code for r in responses]

    after = _invoice_count_for_patient(pg_session_factory, pg_patient)
    assert after == before + 1  # exactly one cart despite three parallel requests
