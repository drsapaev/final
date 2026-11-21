"""Shared synthetic prerequisites for HTTP tests of doctor scheduling."""

import base64
import json
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import event, text

from app.api.v1.endpoints.doctor_integration import _visits
from app.core.config import settings
from app.models.patient import Patient
from app.models.visit import Visit
from app.services.notification_service import NotificationService


def keyed_schedule_headers(headers):
    return {**headers, "Idempotency-Key": f"synthetic-{uuid4()}"}


@pytest.fixture
def mock_invitations(monkeypatch, db_session):
    # create_all-based test databases intentionally omit migration-only
    # clocks; provide only the synthetic writer reservation required here.
    db_session.execute(text("CREATE TABLE IF NOT EXISTS doctor_price_generation_clock (id INTEGER PRIMARY KEY, value INTEGER NOT NULL)"))
    db_session.execute(text("INSERT OR IGNORE INTO doctor_price_generation_clock (id,value) VALUES (1,1)"))
    db_session.commit()
    key = base64.urlsafe_b64encode(b"synthetic-repeat-test-key-32byte").decode("ascii")
    monkeypatch.setattr(settings, "DOCTOR_PRICE_HMAC_KEYS", SecretStr(json.dumps({"1": key})))
    monkeypatch.setattr(settings, "DOCTOR_PRICE_HMAC_ACTIVE_VERSION", 1)
    calls = []

    def initialize_patient(_mapper, _connection, patient):
        if not patient.notification_owner_generation:
            patient.notification_owner_generation = 1

    def initialize_visit(_mapper, _connection, visit):
        if not visit.confirmation_context_epoch:
            visit.confirmation_context_epoch = 1

    # create_all omits the migration triggers that initialize these epochs.
    event.listen(Patient, "before_insert", initialize_patient)
    event.listen(Visit, "before_insert", initialize_visit)

    async def fake_send(self, db, visit_id, channel="auto", expected_context=None):
        calls.append(visit_id)
        return {"success": True, "channel": channel}

    monkeypatch.setattr(NotificationService, "send_visit_confirmation_invitation", fake_send)
    try:
        yield calls
    finally:
        event.remove(Patient, "before_insert", initialize_patient)
        event.remove(Visit, "before_insert", initialize_visit)



def observe_invitation_staging(monkeypatch):
    """Observe the real staging call without replacing the invitation logic."""
    calls = []
    stage = _visits.stage_visit_invitation

    def record(db, **kwargs):
        calls.append((kwargs["visit_id"], kwargs["channel"]))
        return stage(db, **kwargs)

    monkeypatch.setattr(_visits, "stage_visit_invitation", record)
    return calls
