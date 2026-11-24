"""Patient confirmation identifiers must never enter lifecycle log records."""

import logging
from datetime import date
from types import SimpleNamespace

import pytest

from app.models.visit import Visit
from app.services.visit_lifecycle_service import VisitLifecycleService


@pytest.mark.parametrize("identity", [
    "+998001234567",
    "telegram_SYNTHETIC_987654321",
    "pwa_198.51.100.42",
    "123456789012345",
])
def test_patient_actor_and_confirmed_by_are_not_logged(db_session, test_patient, caplog, identity):
    visit = Visit(patient_id=test_patient.id, visit_date=date(2099, 1, 1), status="pending_confirmation")
    db_session.add(visit)
    db_session.flush()
    actor = SimpleNamespace(id=identity)
    service = VisitLifecycleService(db_session)
    with caplog.at_level(logging.INFO, logger="app.services.visit_lifecycle_service"):
        service.confirm_visit(visit.id, actor, confirmed_by=identity, commit=False)
        service.activate_confirmed_visit(visit.id, actor, commit=False)
    db_session.flush()
    db_session.refresh(visit)
    assert visit.confirmed_by == identity
    assert visit.status == "open"
    records = [r for r in caplog.records if r.name == "app.services.visit_lifecycle_service"]
    assert any(r.getMessage().startswith("visit.confirm ") for r in records)
    assert any(r.getMessage().startswith("visit.activate_confirmed ") for r in records)
    assert all(identity not in r.getMessage() and identity not in repr(r.args) for r in records)


def test_real_numeric_staff_id_is_logged_but_confirmation_value_is_not(db_session, test_patient, caplog):
    visit = Visit(patient_id=test_patient.id, visit_date=date(2099, 1, 1), status="pending_confirmation")
    db_session.add(visit)
    db_session.flush()
    secret = "+998009876543"
    actor = SimpleNamespace(id=42)
    service = VisitLifecycleService(db_session)
    with caplog.at_level(logging.INFO, logger="app.services.visit_lifecycle_service"):
        service.confirm_visit(visit.id, actor, confirmed_by=secret, commit=False)
        service.activate_confirmed_visit(visit.id, actor, commit=False)
    db_session.flush()
    db_session.refresh(visit)
    assert visit.confirmed_by == secret
    assert visit.status == "open"
    records = [r for r in caplog.records if r.name == "app.services.visit_lifecycle_service"]
    assert len([r for r in records if "user_id=42" in r.getMessage()]) == 2
    assert all(secret not in r.getMessage() and secret not in repr(r.args) for r in records)
