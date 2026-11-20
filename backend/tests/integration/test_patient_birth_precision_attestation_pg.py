"""HTTP date attestation against the actual 0110 trigger on synthetic PG."""

import importlib.util
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema


@pytest.mark.integration
@pytest.mark.parametrize("logout_endpoint", ["review", "attest"])
def test_postgres_actual_trigger_rejects_aba_and_allows_fresh_review(monkeypatch, logout_endpoint):
    import jwt

    import app.db.base  # noqa: F401
    from app.api.deps import get_db
    from app.api.v1.endpoints import patients as patients_endpoint
    from app.core.config import settings
    from app.db.base_class import Base
    from app.main import app
    from app.models.audit import AuditLog
    from app.models.authentication import TokenBlacklist
    from app.models.patient import Patient, PatientBirthDateEvidence
    from app.models.user import User
    from tests.conftest import mint_access_token

    raw = os.environ.get("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql":
        pytest.skip("requires disposable PostgreSQL")
    url = make_url(raw)
    if not (url.database or "").startswith("clinic_test") and os.environ.get("CI", "").lower() != "true":
        pytest.skip("requires a disposable clinic_test database")
    schema = "test_birth_http_" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -clock_timeout=10000"})
    try:
        Base.metadata.create_all(engine)
        # Install actual migration after removing its create_all equivalents.
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE patient_birth_date_evidence"))
            conn.execute(text("ALTER TABLE patients DROP CONSTRAINT ck_patient_birth_date_precision"))
            conn.execute(text("ALTER TABLE patients DROP COLUMN birth_date_precision"))
            conn.execute(text("ALTER TABLE patients DROP COLUMN birth_date_generation"))
            path = Path(__file__).resolve().parents[2] / "alembic/versions/0110_patient_birth_precision.py"
            spec = importlib.util.spec_from_file_location("test_actual_birth_migration", path)
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
        with Session(engine, expire_on_commit=False) as db:
            actor = User(username="synthetic-admin", email="admin@invalid.example", full_name="Synthetic",
                         hashed_password="synthetic", role="Admin", is_active=True, is_superuser=True)
            patient = Patient(first_name="Synthetic", last_name="Patient", birth_date=date(2000, 1, 1))
            db.add_all([actor, patient])
            db.commit()
            patient_id, actor_id = patient.id, actor.id
            token = mint_access_token(actor)
            headers = {"Authorization": f"Bearer {token}"}

        def override_db():
            with Session(engine) as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        with TestClient(app) as client:
            path = f"/api/v1/patients/{patient_id}/birth-date"
            review = client.post(path + "/review", headers=headers)
            assert review.status_code == 200, review.text
            old = review.json()

            def attest(review_data):
                return client.post(path + "/attest", headers=headers, json={
                    "confirmed_exact_date": True, "expected_generation": review_data["generation"],
                    "review_expires_at": review_data["review_expires_at"], "token": review_data["token"],
                })

            with Session(engine) as db:
                db.delete(db.get(Patient, patient_id))
                db.commit()
                db.add(Patient(id=patient_id, first_name="Synthetic", last_name="Replacement",
                               birth_date=date(2000, 1, 1)))
                db.commit()
                assert db.get(Patient, patient_id).birth_date_generation > old["generation"]
            assert attest(old).status_code == 409
            new_review = client.post(path + "/review", headers=headers)
            assert new_review.status_code == 200, new_review.text
            old = new_review.json()
            with Session(engine) as db:
                patient = db.get(Patient, patient_id)
                patient.birth_date = date(2000, 2, 1)
                db.commit()
                patient.birth_date = date(2000, 1, 1)
                db.commit()
                db.refresh(patient)
                assert patient.birth_date_generation == old["generation"] + 2

            stale = attest(old)
            assert stale.status_code == 409 and "no-store" in stale.headers["cache-control"]
            fresh = client.post(path + "/review", headers=headers)
            assert fresh.status_code == 200, fresh.text
            result = attest(fresh.json())
            assert result.status_code == 200, result.text

            with Session(engine, expire_on_commit=False) as db:
                other = Patient(first_name="Synthetic", last_name="Other", birth_date=date(2001, 2, 3))
                db.add(other)
                db.commit()
                other_id = other.id
            other_path = f"/api/v1/patients/{other_id}/birth-date"
            other_review = client.post(other_path + "/review", headers=headers)
            assert other_review.status_code == 200, other_review.text
            other_payload = other_review.json()
            started, pids = threading.Event(), []
            actual_lock = patients_endpoint._birth_review_context

            def marked_lock(db, bearer, requested_patient):
                pids.append(db.execute(text("SELECT pg_backend_pid() ")).scalar_one())
                started.set()
                return actual_lock(db, bearer, requested_patient)

            monkeypatch.setattr(patients_endpoint, "_birth_review_context", marked_lock)
            claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

            def request_worker():
                if logout_endpoint == "review":
                    return client.post(other_path + "/review", headers=headers)
                return client.post(other_path + "/attest", headers=headers, json={
                    "confirmed_exact_date": True, "expected_generation": other_payload["generation"],
                    "review_expires_at": other_payload["review_expires_at"], "token": other_payload["token"],
                })

            with Session(engine) as logout:
                logout.query(User).filter_by(id=actor_id).with_for_update().one()
                logout.add(TokenBlacklist(jti=claims["jti"], user_id=actor_id,
                                          expires_at=datetime.fromtimestamp(claims["exp"], UTC), reason="logout"))
                logout.flush()
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(request_worker)
                    try:
                        assert started.wait(5)
                        deadline = time.monotonic() + 8
                        while time.monotonic() < deadline:
                            assert not future.done()
                            with engine.connect() as observer:
                                if observer.execute(text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pids[0]}).scalar_one():
                                    break
                            time.sleep(0.02)
                        else:
                            pytest.fail("review did not wait for logout's User lock")
                    finally:
                        logout.commit()
                    rejected = future.result(timeout=12)
            assert rejected.status_code == 401, rejected.text
            assert "no-store" in rejected.headers.get("cache-control", "").lower()
        with Session(engine) as db:
            assert db.query(PatientBirthDateEvidence).filter_by(patient_id=patient_id).count() == 1
            assert db.query(AuditLog).filter_by(action="patient_birth_date_attested", entity_id=patient_id).count() == 1
            assert db.query(PatientBirthDateEvidence).filter_by(patient_id=other_id).count() == 0
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()
