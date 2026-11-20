"""Synthetic admin reissue uses durable intents without exposing the bearer."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import OperationalError

from app.models.all_free_request import AllFreeRequest
from app.models.audit import AuditLog
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.models.visit import Visit, VisitService
from app.models.visit_invitation_delivery import VisitInvitationDelivery
from tests.integration.test_encounter_migration_pg import _migration


@pytest.fixture
def subject(db_session, test_patient, test_visit):
    test_patient.notification_owner_generation = 31
    test_visit.confirmation_context_epoch = 41
    test_visit.confirmation_token = "SYNTHETIC-original-token"
    test_visit.confirmation_channel = "telegram"
    test_visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
    db_session.add(VisitService(visit_id=test_visit.id, service_id=1, name="SYNTHETIC CURRENCY",
                                qty=1, price=Decimal("0.00"), currency="UZS"))
    db_session.commit()
    migration = _migration("0115_confirmation_trigger_path.py")
    migration.op = Operations(MigrationContext.configure(db_session.connection()))
    migration.upgrade()
    return test_patient.id, test_visit.id


def _review(client, headers, visit_id):
    response = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue/review", headers=headers)
    assert response.status_code == 200, response.text
    assert "no-store" in response.headers["cache-control"]
    return response.json()


def _payload(review, channel="pwa"):
    return {"expected_patient_id": review["patient_id"], "expected_owner_generation": review["owner_generation"],
            "expected_context_epoch": review["context_epoch"], "channel": channel, "token": review["token"]}


def test_admin_reissue_stages_once_and_replay_keeps_context(client, db_session, subject, admin_auth_headers):
    patient_id, visit_id = subject
    review = _review(client, admin_auth_headers, visit_id)
    key = str(uuid.uuid4())
    headers = {**admin_auth_headers, "Idempotency-Key": key}
    response = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=headers, json=_payload(review))
    assert response.status_code == 200, response.text
    assert "no-store" in response.headers["cache-control"]
    body = response.json()
    assert body["state"] == "pending" and not body["idempotent_replay"] and "token" not in body
    visit = db_session.get(Visit, visit_id)
    db_session.refresh(visit)
    assert visit.confirmation_token and visit.confirmation_token != "SYNTHETIC-original-token"
    assert visit.confirmation_token not in response.text
    stored_token = visit.confirmation_token
    delivery = db_session.get(VisitInvitationDelivery, body["delivery_id"])
    assert delivery.patient_id == patient_id and delivery.state == "pending" and stored_token not in repr(delivery.__dict__)
    repeat = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=headers, json=_payload(review))
    assert repeat.status_code == 200, repeat.text
    assert repeat.json() == {"delivery_id": delivery.id, "state": "pending", "idempotent_replay": True}
    db_session.refresh(visit)
    assert visit.confirmation_token == stored_token
    assert db_session.query(VisitInvitationDelivery).filter_by(visit_id=visit_id).count() == 1
    assert db_session.query(AuditLog).filter_by(action="visit_invitation_reissued", entity_id=visit_id).count() == 1
    changed = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=headers, json=_payload(review, "phone"))
    assert changed.status_code == 409


@pytest.mark.parametrize("state", ["pending", "unknown"])
@pytest.mark.parametrize("other_admin", [False, True])
def test_another_key_cannot_replace_unresolved_invitation(
    client, db_session, subject, admin_auth_headers, state, other_admin
):
    from app.models.user import User
    from tests.conftest import mint_access_token

    _, visit_id = subject
    first_review = _review(client, admin_auth_headers, visit_id)
    first_headers = {**admin_auth_headers, "Idempotency-Key": str(uuid.uuid4())}
    first = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue",
                        headers=first_headers, json=_payload(first_review))
    assert first.status_code == 200, first.text
    delivery = db_session.get(VisitInvitationDelivery, first.json()["delivery_id"])
    if state == "unknown":
        delivery.state = "unknown"
        db_session.commit()
    visit = db_session.get(Visit, visit_id)
    db_session.refresh(visit)
    original_token, original_expiry = visit.confirmation_token, visit.confirmation_expires_at
    next_headers = admin_auth_headers
    if other_admin:
        other = User(username=f"synthetic-reissue-admin-{uuid.uuid4().hex}", hashed_password="!",
                     role="Admin", is_active=True)
        db_session.add(other)
        db_session.commit()
        next_headers = {"Authorization": f"Bearer {mint_access_token(other)}"}
    next_review = _review(client, next_headers, visit_id)
    retry = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue",
                        headers={**next_headers, "Idempotency-Key": str(uuid.uuid4())},
                        json=_payload(next_review))
    assert retry.status_code == 409, retry.text
    assert "no-store" in retry.headers["cache-control"]
    db_session.expire_all()
    visit = db_session.get(Visit, visit_id)
    assert (visit.confirmation_token, visit.confirmation_expires_at) == (original_token, original_expiry)
    assert db_session.query(VisitInvitationDelivery).filter_by(visit_id=visit_id).count() == 1
    replay = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue",
                         headers=first_headers, json=_payload(first_review))
    assert replay.status_code == 200 and replay.json()["state"] == state
    assert replay.json()["idempotent_replay"] is True


def test_known_sent_attempt_allows_an_explicit_new_reissue(client, db_session, subject, admin_auth_headers):
    _, visit_id = subject
    first_review = _review(client, admin_auth_headers, visit_id)
    first = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue",
                        headers={**admin_auth_headers, "Idempotency-Key": str(uuid.uuid4())},
                        json=_payload(first_review))
    assert first.status_code == 200, first.text
    db_session.get(VisitInvitationDelivery, first.json()["delivery_id"]).state = "sent"
    db_session.commit()
    next_review = _review(client, admin_auth_headers, visit_id)
    second = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue",
                         headers={**admin_auth_headers, "Idempotency-Key": str(uuid.uuid4())},
                         json=_payload(next_review))
    assert second.status_code == 200, second.text
    assert second.json()["delivery_id"] != first.json()["delivery_id"]


def test_review_displays_locked_snapshot_and_rejects_forged_or_changed_context(
    client, db_session, subject, admin_auth_headers, caplog
):
    patient_id, visit_id = subject
    visit = db_session.get(Visit, visit_id)
    db_session.add(VisitService(visit_id=visit_id, service_id=1, name="SYNTHETIC REVIEW SERVICE",
                                qty=3, price=Decimal("0.07"), currency="UZS"))
    db_session.flush()
    db_session.refresh(visit)
    visit.confirmation_token = "SYNTHETIC-review-original-token"
    visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
    db_session.commit()
    review = _review(client, admin_auth_headers, visit_id)
    assert review["patient_id"] == patient_id
    assert review["patient_name"] == db_session.get(Patient, patient_id).short_name()
    assert review["visit_date"] == visit.visit_date.isoformat()
    assert review["visit_time"] == visit.visit_time
    review_service = next(item for item in review["services"] if item["name"] == "SYNTHETIC REVIEW SERVICE")
    assert review_service["quantity"] == 3
    assert review_service["total"] == 0.21
    assert review["total_amount"] == 0.21
    assert review["token"] != "SYNTHETIC-review-original-token"
    assert review["token"] not in caplog.text
    headers = {**admin_auth_headers, "Idempotency-Key": str(uuid.uuid4())}
    forged = _payload(review)
    forged["token"] = forged["token"][:-1] + ("0" if forged["token"][-1] != "0" else "1")
    response = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=headers, json=forged)
    assert response.status_code == 409
    assert "no-store" in response.headers["cache-control"]
    patient = db_session.get(Patient, patient_id)
    patient.first_name = "SYNTHETIC-CHANGED-NAME"
    db_session.commit()
    response = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=headers, json=_payload(review))
    assert response.status_code == 409
    assert db_session.query(VisitInvitationDelivery).filter_by(visit_id=visit_id).count() == 0
    assert db_session.get(Visit, visit_id).confirmation_token == "SYNTHETIC-review-original-token"
    assert review["token"] not in caplog.text


def test_review_and_replay_are_bound_to_the_original_session(client, db_session, subject, admin_user, admin_auth_headers):
    from tests.conftest import mint_access_token

    _, visit_id = subject
    review = _review(client, admin_auth_headers, visit_id)
    key = str(uuid.uuid4())
    original = {**admin_auth_headers, "Idempotency-Key": key}
    other = {"Authorization": f"Bearer {mint_access_token(admin_user)}", "Idempotency-Key": key}
    before = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=other, json=_payload(review))
    assert before.status_code == 409
    first = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=original, json=_payload(review))
    assert first.status_code == 200, first.text
    replay_other = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=other, json=_payload(review))
    assert replay_other.status_code == 409
    replay_original = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=original, json=_payload(review))
    assert replay_original.status_code == 200 and replay_original.json()["idempotent_replay"] is True
    assert db_session.query(VisitInvitationDelivery).filter_by(visit_id=visit_id).count() == 1


def test_expired_review_proof_cannot_issue(client, db_session, subject, admin_auth_headers, monkeypatch):
    from app.api.v1.endpoints import visit_confirmation

    _, visit_id = subject
    review = _review(client, admin_auth_headers, visit_id)

    class Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(tz) + timedelta(minutes=6)

    monkeypatch.setattr(visit_confirmation, "datetime", Later)
    headers = {**admin_auth_headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=headers, json=_payload(review))
    assert response.status_code == 409
    assert db_session.query(VisitInvitationDelivery).filter_by(visit_id=visit_id).count() == 0


def test_review_proof_rejects_token_rotation_without_context_epoch_change(client, db_session, subject, admin_auth_headers):
    _, visit_id = subject
    review = _review(client, admin_auth_headers, visit_id)
    visit = db_session.get(Visit, visit_id)
    visit.confirmation_token = "SYNTHETIC-rotated-token"
    db_session.commit()
    db_session.refresh(visit)
    assert visit.confirmation_context_epoch == review["context_epoch"]
    headers = {**admin_auth_headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=headers, json=_payload(review))
    assert response.status_code == 409
    assert db_session.query(VisitInvitationDelivery).filter_by(visit_id=visit_id).count() == 0
    assert db_session.get(Visit, visit_id).confirmation_token == "SYNTHETIC-rotated-token"


def test_benefit_review_remains_closed_until_decision_versions_exist(client, db_session, admin_auth_headers):
    from tests.integration.test_confirmation_benefit_quote import _discounted_review

    visit_id, _ = _discounted_review(db_session)
    patient = db_session.get(Patient, db_session.get(Visit, visit_id).patient_id)
    patient.notification_owner_generation = 31
    db_session.commit()
    response = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue/review", headers=admin_auth_headers)
    assert response.status_code == 409
    assert response.json()["detail"] == "Льгота требует повторной проверки"
    assert "no-store" in response.headers["cache-control"]
    assert "token" not in response.json()


def test_undeliverable_and_stale_context_roll_back(client, db_session, subject, admin_auth_headers):
    patient_id, visit_id = subject
    review = _review(client, admin_auth_headers, visit_id)
    before = db_session.get(Visit, visit_id).confirmation_token
    headers = {**admin_auth_headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=headers, json=_payload(review, "telegram"))
    assert response.status_code == 409, response.text
    db_session.expire_all()
    assert db_session.get(Visit, visit_id).confirmation_token == before
    assert db_session.query(VisitInvitationDelivery).filter_by(visit_id=visit_id).count() == 0
    stale = _payload(review)
    stale["expected_owner_generation"] += 1
    response = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=headers, json=stale)
    assert response.status_code == 409 and "no-store" in response.headers["cache-control"]


def test_sibling_pending_blocks_reissue_and_confirmation(client, db_session, subject, admin_user, admin_auth_headers):
    patient_id, visit_id = subject
    encounter = Encounter(patient_id=patient_id, provenance="new", generation=9)
    db_session.add(encounter)
    db_session.flush()
    visit = db_session.get(Visit, visit_id)
    visit.encounter_id = encounter.id
    sibling = Visit(patient_id=patient_id, encounter_id=encounter.id, visit_date=visit.visit_date,
                    status="pending_confirmation", confirmation_context_epoch=55,
                    confirmation_token="SYNTHETIC-sibling", confirmation_expires_at=datetime.now(UTC) + timedelta(hours=1))
    db_session.add(sibling)
    db_session.flush()
    db_session.commit()
    review = _review(client, admin_auth_headers, visit_id)
    db_session.add(AllFreeRequest(visit_id=sibling.id, patient_id=patient_id, encounter_id=encounter.id,
        visit_id_snapshot=sibling.id, patient_id_snapshot=patient_id, encounter_id_snapshot=encounter.id,
        visit_context_epoch=55, encounter_generation=9, baseline_total=Decimal("10.00"), status="pending",
        requested_by_user_id=admin_user.id, requested_by_user_id_snapshot=admin_user.id,
        requested_by_role_snapshot="Admin", policy_auto_approve=False))
    db_session.commit()
    token = db_session.get(Visit, visit_id).confirmation_token
    pending_review = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue/review", headers=admin_auth_headers)
    assert pending_review.status_code == 409 and "no-store" in pending_review.headers["cache-control"]
    headers = {**admin_auth_headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=headers, json=_payload(review))
    assert response.status_code == 409
    info = client.post("/api/v1/visits/info", json={"token": token})
    assert info.status_code == 409
    db_session.expire_all()
    assert db_session.get(Visit, visit_id).confirmation_token == token


def test_sibling_context_change_invalidates_review_without_changing_target_epoch(client, db_session, subject, admin_auth_headers):
    patient_id, visit_id = subject
    encounter = Encounter(patient_id=patient_id, provenance="new", generation=9)
    db_session.add(encounter)
    db_session.flush()
    visit = db_session.get(Visit, visit_id)
    visit.encounter_id = encounter.id
    sibling = Visit(patient_id=patient_id, encounter_id=encounter.id, visit_date=visit.visit_date,
                    status="pending_confirmation", confirmation_context_epoch=55,
                    confirmation_token="SYNTHETIC-sibling-token", confirmation_expires_at=datetime.now(UTC) + timedelta(hours=1))
    db_session.add(sibling)
    db_session.commit()
    review = _review(client, admin_auth_headers, visit_id)
    sibling.visit_date += timedelta(days=1)
    db_session.commit()
    db_session.refresh(visit)
    assert visit.confirmation_context_epoch == review["context_epoch"]
    headers = {**admin_auth_headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=headers, json=_payload(review))
    assert response.status_code == 409
    assert db_session.query(VisitInvitationDelivery).filter_by(visit_id=visit_id).count() == 0


def test_invalid_request_returns_no_store(client, subject, admin_auth_headers):
    _, visit_id = subject
    response = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=admin_auth_headers, json={})
    assert response.status_code == 422
    assert "no-store" in response.headers["cache-control"]


def test_replay_rechecks_subject_owner(client, db_session, subject, admin_auth_headers):
    patient_id, visit_id = subject
    review = _review(client, admin_auth_headers, visit_id)
    headers = {**admin_auth_headers, "Idempotency-Key": str(uuid.uuid4())}
    first = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=headers, json=_payload(review))
    assert first.status_code == 200, first.text
    from app.models.patient import Patient

    patient = db_session.get(Patient, patient_id)
    patient.notification_owner_generation += 1
    db_session.commit()
    replay = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=headers, json=_payload(review))
    assert replay.status_code == 409 and "no-store" in replay.headers["cache-control"]


def test_replay_rechecks_admin_revocation(client, db_session, subject, admin_user, admin_auth_headers):
    _, visit_id = subject
    review = _review(client, admin_auth_headers, visit_id)
    headers = {**admin_auth_headers, "Idempotency-Key": str(uuid.uuid4())}
    first = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=headers, json=_payload(review))
    assert first.status_code == 200, first.text
    admin_user.is_active = False
    db_session.commit()
    replay = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=headers, json=_payload(review))
    assert replay.status_code in (401, 403)


def test_replay_rechecks_individual_logout(client, db_session, subject, admin_user, admin_auth_headers):
    import jwt

    from app.core.config import settings
    from app.services.token_blacklist_service import token_blacklist_service

    _, visit_id = subject
    review = _review(client, admin_auth_headers, visit_id)
    headers = {**admin_auth_headers, "Idempotency-Key": str(uuid.uuid4())}
    first = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=headers, json=_payload(review))
    assert first.status_code == 200, first.text
    claims = jwt.decode(admin_auth_headers["Authorization"].split()[1], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert token_blacklist_service.blacklist_token(db_session, claims["jti"],
        datetime.fromtimestamp(claims["exp"], UTC), user_id=admin_user.id)
    replay = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=headers, json=_payload(review))
    assert replay.status_code in (401, 403)
    assert db_session.query(VisitInvitationDelivery).filter_by(visit_id=visit_id).count() == 1


@pytest.mark.parametrize("sqlstate,expected", [("40P01", 409), ("55P03", 409), ("22000", 500)])
def test_lock_error_rolls_back_without_exposing_database_detail(client, db_session, subject, admin_auth_headers, monkeypatch, sqlstate, expected):
    from app.api.v1.endpoints import visit_confirmation

    _, visit_id = subject
    review = _review(client, admin_auth_headers, visit_id)
    original = db_session.get(Visit, visit_id).confirmation_token

    class SyntheticDbError(Exception):
        def __init__(self, state):
            self.sqlstate = state

    def raise_conflict(*_args):
        raise OperationalError("SYNTHETIC statement", {}, SyntheticDbError(sqlstate))

    monkeypatch.setattr(visit_confirmation, "lock_group_without_pending", raise_conflict)
    headers = {**admin_auth_headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=headers, json=_payload(review))
    assert response.status_code == expected and "SYNTHETIC statement" not in response.text
    db_session.expire_all()
    assert db_session.get(Visit, visit_id).confirmation_token == original
    assert db_session.query(VisitInvitationDelivery).filter_by(visit_id=visit_id).count() == 0


@pytest.mark.parametrize("currency", [None, "USD", "UZS"])
def test_review_displays_actual_currency(client, db_session, subject, admin_auth_headers, currency):
    _, visit_id = subject
    db_session.query(VisitService).filter_by(visit_id=visit_id).delete(synchronize_session=False)
    db_session.add(VisitService(visit_id=visit_id, service_id=1, name="SYNTHETIC", qty=1,
                                price=Decimal("1.00"), currency=currency))
    db_session.flush()
    visit = db_session.get(Visit, visit_id)
    db_session.refresh(visit)
    visit.confirmation_token = "SYNTHETIC-currency-review-token"
    visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
    db_session.commit()
    response = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue/review", headers=admin_auth_headers)
    if currency is None:
        assert response.status_code == 409
        assert "token" not in response.json()
    else:
        assert response.status_code == 200, response.text
        assert response.json()["currency"] == currency
        assert response.json()["total_amount"] == 1.0


def test_review_refuses_mixed_currencies(client, db_session, subject, admin_auth_headers):
    _, visit_id = subject
    for currency in ("UZS", "USD"):
        db_session.add(VisitService(visit_id=visit_id, service_id=1, name="SYNTHETIC", qty=1,
                                    price=Decimal("1.00"), currency=currency))
    db_session.commit()
    response = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue/review", headers=admin_auth_headers)
    assert response.status_code == 409
    assert "no-store" in response.headers["cache-control"]


def test_review_proof_rejects_changed_currency(client, db_session, subject, admin_auth_headers):
    _, visit_id = subject
    review = _review(client, admin_auth_headers, visit_id)
    line = db_session.query(VisitService).filter_by(visit_id=visit_id).one()
    line.currency = "USD"
    db_session.commit()
    headers = {**admin_auth_headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post(f"/api/v1/visits/{visit_id}/confirmation-reissue", headers=headers, json=_payload(review))
    assert response.status_code == 409
    assert db_session.query(VisitInvitationDelivery).filter_by(visit_id=visit_id).count() == 0
