"""Staff confirmation must serialize with pending all-free decisions."""

from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import OperationalError

from app.graphql import mutations
from app.models.all_free_request import AllFreeRequest
from app.models.encounter import Encounter
from app.models.visit import Visit, VisitService


def _seed(db, patient, actor, *, pending: bool, sibling: bool = False):
    encounter = Encounter(patient_id=patient.id, provenance="new")
    db.add(encounter)
    db.flush()
    visit = Visit(patient_id=patient.id, encounter_id=encounter.id, visit_date=date(2099, 1, 1),
                  status="pending_confirmation", confirmation_context_epoch=7, source="desk")
    db.add(visit)
    db.flush()
    target = visit
    if sibling:
        target = Visit(patient_id=patient.id, encounter_id=encounter.id, visit_date=date(2099, 1, 1),
                       status="pending_confirmation", confirmation_context_epoch=8, source="desk")
        db.add(target)
        db.flush()
    db.add(VisitService(visit_id=target.id, service_id=123, name="SYNTHETIC", price=Decimal("9.00"), qty=1, currency="UZS"))
    if pending:
        db.add(AllFreeRequest(visit_id=target.id, patient_id=patient.id, encounter_id=encounter.id,
            visit_id_snapshot=target.id, patient_id_snapshot=patient.id, encounter_id_snapshot=encounter.id,
            visit_context_epoch=target.confirmation_context_epoch, encounter_generation=encounter.generation,
            baseline_total=Decimal("9.00"), status="pending", requested_by_user_id=actor.id,
            requested_by_user_id_snapshot=actor.id, requested_by_role_snapshot="Admin", policy_auto_approve=False))
    db.commit()
    return visit.id


def _graphql(client, visit_id, headers):
    return client.post("/api/graphql", headers=headers, json={"query":
        'mutation($id:Int!){updateVisitStatus(id:$id,status:"confirmed"){success message errors}}',
        "variables": {"id": visit_id}})


@pytest.mark.parametrize("surface", ["registrar", "graphql", "batch"])
@pytest.mark.parametrize("sibling", [False, True])
def test_pending_blocks_staff_confirmation_and_batch_mutations(
    client, db_session, admin_user, admin_auth_headers, test_patient, monkeypatch, surface, sibling
):
    visit_id = _seed(db_session, test_patient, admin_user, pending=True, sibling=sibling)
    patient_id = test_patient.id
    @contextmanager
    def graphql_session():
        yield db_session
    monkeypatch.setattr(mutations, "get_db_session", graphql_session)
    if surface == "registrar":
        response = client.post(f"/api/v1/registrar/visits/{visit_id}/confirm", headers=admin_auth_headers, json={})
        assert response.status_code == 409, response.text
    elif surface == "graphql":
        response = _graphql(client, visit_id, admin_auth_headers)
        assert response.status_code == 200, response.text
        assert response.json()["data"]["updateVisitStatus"]["success"] is False
    else:
        response = client.patch(f"/api/v1/registrar/batch/patients/{patient_id}/entries/2099-01-01",
            headers=admin_auth_headers, json={"entries": [{"id": visit_id, "entry_type": "visit", "action": "update", "status": "confirmed"}],
                                             "common_updates": {"notes": "MUST NOT COMMIT"}})
        assert response.status_code == 409, response.text
    db_session.expire_all()
    visit = db_session.get(Visit, visit_id)
    assert visit.status == "pending_confirmation" and visit.notes != "MUST NOT COMMIT"


@pytest.mark.parametrize("surface", ["registrar", "graphql", "batch"])
def test_staff_confirmation_without_pending_remains_available(
    client, db_session, admin_user, admin_auth_headers, test_patient, monkeypatch, surface
):
    visit_id = _seed(db_session, test_patient, admin_user, pending=False)
    patient_id = test_patient.id
    @contextmanager
    def graphql_session():
        yield db_session
    monkeypatch.setattr(mutations, "get_db_session", graphql_session)
    if surface == "registrar":
        response = client.post(f"/api/v1/registrar/visits/{visit_id}/confirm", headers=admin_auth_headers, json={})
        assert response.status_code == 200, response.text
    elif surface == "graphql":
        response = _graphql(client, visit_id, admin_auth_headers)
        assert response.status_code == 200 and response.json()["data"]["updateVisitStatus"]["success"] is True, response.text
    else:
        response = client.patch(f"/api/v1/registrar/batch/patients/{patient_id}/entries/2099-01-01", headers=admin_auth_headers,
            json={"entries": [{"id": visit_id, "entry_type": "visit", "action": "update", "status": "confirmed"}]})
        assert response.status_code == 200, response.text
    db_session.expire_all()
    assert db_session.get(Visit, visit_id).status == "confirmed"


@pytest.mark.parametrize("surface", ["registrar", "graphql", "batch"])
@pytest.mark.parametrize("currency_case", ["unknown", "mixed"])
def test_staff_confirmation_requires_proven_currency(
    client, db_session, admin_user, admin_auth_headers, test_patient, monkeypatch, surface, currency_case
):
    visit_id = _seed(db_session, test_patient, admin_user, pending=False)
    if currency_case == "unknown":
        db_session.query(VisitService).filter_by(visit_id=visit_id).one().currency = None
    else:
        db_session.add(VisitService(visit_id=visit_id, service_id=124, name="SYNTHETIC",
                                    price=Decimal("1.00"), qty=1, currency="USD"))
    db_session.commit()

    @contextmanager
    def graphql_session():
        yield db_session

    monkeypatch.setattr(mutations, "get_db_session", graphql_session)
    if surface == "registrar":
        response = client.post(f"/api/v1/registrar/visits/{visit_id}/confirm", headers=admin_auth_headers, json={})
        assert response.status_code == 409, response.text
    elif surface == "graphql":
        response = _graphql(client, visit_id, admin_auth_headers)
        assert response.status_code == 200 and response.json()["data"]["updateVisitStatus"]["success"] is False
    else:
        response = client.patch(f"/api/v1/registrar/batch/patients/{test_patient.id}/entries/2099-01-01",
            headers=admin_auth_headers,
            json={"entries": [{"id": visit_id, "entry_type": "visit", "action": "update", "status": "confirmed"}],
                  "common_updates": {"notes": "MUST NOT COMMIT"}})
        assert response.status_code == 409, response.text
    db_session.expire_all()
    visit = db_session.get(Visit, visit_id)
    assert visit.status == "pending_confirmation" and visit.notes != "MUST NOT COMMIT"


def test_batch_rolls_back_all_groups_when_later_visit_is_blocked(
    client, db_session, admin_user, admin_auth_headers, test_patient
):
    first = _seed(db_session, test_patient, admin_user, pending=False)
    second = _seed(db_session, test_patient, admin_user, pending=True)
    response = client.patch(
        f"/api/v1/registrar/batch/patients/{test_patient.id}/entries/2099-01-01",
        headers=admin_auth_headers,
        json={"entries": [
            {"id": first, "entry_type": "visit", "action": "update", "status": "confirmed"},
            {"id": second, "entry_type": "visit", "action": "update", "status": "confirmed"},
        ], "common_updates": {"notes": "MUST NOT COMMIT"}},
    )
    assert response.status_code == 409, response.text
    db_session.expire_all()
    for visit_id in (first, second):
        visit = db_session.get(Visit, visit_id)
        assert visit.status == "pending_confirmation" and visit.notes != "MUST NOT COMMIT"


def test_batch_checks_each_visit_currency_before_any_mutation(
    client, db_session, admin_user, admin_auth_headers, test_patient
):
    first = _seed(db_session, test_patient, admin_user, pending=False)
    second = _seed(db_session, test_patient, admin_user, pending=False)
    db_session.query(VisitService).filter_by(visit_id=second).one().currency = None
    db_session.commit()
    response = client.patch(
        f"/api/v1/registrar/batch/patients/{test_patient.id}/entries/2099-01-01",
        headers=admin_auth_headers,
        json={"entries": [
            {"id": first, "entry_type": "visit", "action": "update", "status": "confirmed"},
            {"id": second, "entry_type": "visit", "action": "update", "status": "confirmed"},
        ], "common_updates": {"notes": "MUST NOT COMMIT"}},
    )
    assert response.status_code == 409, response.text
    db_session.expire_all()
    for visit_id in (first, second):
        visit = db_session.get(Visit, visit_id)
        assert visit.status == "pending_confirmation" and visit.notes != "MUST NOT COMMIT"


@pytest.mark.parametrize("sqlstate", ["40P01", "55P03"])
def test_batch_commit_lock_conflict_rolls_back_and_returns_409(
    client, db_session, admin_user, admin_auth_headers, test_patient, monkeypatch, sqlstate
):
    visit_id = _seed(db_session, test_patient, admin_user, pending=False)
    patient_id = test_patient.id

    class SyntheticLockError(Exception):
        pass

    original = SyntheticLockError("synthetic lock conflict")
    original.sqlstate = sqlstate
    def fail_commit():
        raise OperationalError("synthetic", {}, original)
    monkeypatch.setattr(db_session, "commit", fail_commit)
    response = client.patch(
        f"/api/v1/registrar/batch/patients/{patient_id}/entries/2099-01-01",
        headers=admin_auth_headers,
        json={"entries": [{"id": visit_id, "entry_type": "visit", "action": "update", "status": "confirmed"}]},
    )
    assert response.status_code == 409 and "synthetic lock conflict" not in response.text
    db_session.expire_all()
    assert db_session.get(Visit, visit_id).status == "pending_confirmation"


def test_batch_other_database_error_is_not_reported_as_lock_conflict(
    client, db_session, admin_user, admin_auth_headers, test_patient, monkeypatch
):
    visit_id = _seed(db_session, test_patient, admin_user, pending=False)
    patient_id = test_patient.id

    class SyntheticDatabaseError(Exception):
        sqlstate = "08006"

    def fail_commit():
        raise OperationalError("synthetic", {}, SyntheticDatabaseError("synthetic failure"))
    monkeypatch.setattr(db_session, "commit", fail_commit)
    response = client.patch(
        f"/api/v1/registrar/batch/patients/{patient_id}/entries/2099-01-01",
        headers=admin_auth_headers,
        json={"entries": [{"id": visit_id, "entry_type": "visit", "action": "update", "status": "confirmed"}]},
    )
    # The application-wide database handler maps connectivity errors to 503.
    assert response.status_code == 503
    assert "synthetic failure" not in response.text
    db_session.expire_all()
    assert db_session.get(Visit, visit_id).status == "pending_confirmation"


def test_revoked_admin_session_cannot_confirm(client, db_session, admin_user, test_patient):
    import jwt

    from app.core.config import settings
    from app.models.authentication import TokenBlacklist
    from tests.conftest import mint_access_token

    visit_id = _seed(db_session, test_patient, admin_user, pending=False)
    token = mint_access_token(admin_user)
    claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    db_session.add(TokenBlacklist(jti=claims["jti"], user_id=admin_user.id,
                                  expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
    db_session.commit()
    response = client.post(f"/api/v1/registrar/visits/{visit_id}/confirm",
                           headers={"Authorization": f"Bearer {token}"}, json={})
    assert response.status_code in (401, 403)
    db_session.expire_all()
    assert db_session.get(Visit, visit_id).status == "pending_confirmation"


@pytest.mark.parametrize("revocation", ["jti", "epoch", "deactivate", "role"])
def test_staff_rechecks_session_after_dependency_before_confirmation(
    client, db_session, admin_user, admin_auth_headers, test_patient, monkeypatch, revocation
):
    from app.models.authentication import TokenBlacklist
    from app.services import profile_contact_security

    visit_id = _seed(db_session, test_patient, admin_user, pending=False)
    capture = profile_contact_security.capture_profile_bearer

    def capture_then_revoke(request, actor):
        bearer = capture(request, actor)
        if revocation == "jti":
            db_session.add(TokenBlacklist(jti=bearer.jti, user_id=actor.id,
                expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
        elif revocation == "epoch":
            actor.auth_epoch += 1
        elif revocation == "deactivate":
            actor.is_active = False
        else:
            actor.role = "Doctor"
            actor.is_superuser = False
        db_session.flush()
        return bearer

    monkeypatch.setattr(profile_contact_security, "capture_profile_bearer", capture_then_revoke)
    response = client.post(f"/api/v1/registrar/visits/{visit_id}/confirm", headers=admin_auth_headers, json={})
    assert response.status_code in (401, 403), response.text
    db_session.expire_all()
    assert db_session.get(Visit, visit_id).status == "pending_confirmation"
