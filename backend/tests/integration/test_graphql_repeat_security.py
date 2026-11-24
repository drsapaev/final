"""GraphQL repeat pricing uses verified evidence and server-owned cents."""
from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.crud.clinic import clinic_today
from app.main import app
from app.models.clinic import ClinicSettings
from app.models.visit import Visit, VisitService
from tests.conftest import mint_access_token
from tests.integration.test_graphql_resolvers_real_db import (
    gql_data,  # noqa: F401
    gql_session_factory,  # noqa: F401
)

QUERY = """mutation($input: VisitInput!) {
  createVisit(input: $input) { success message errors visit { id discountMode } }
}"""


@pytest.fixture
def graph_client(gql_data, gql_session_factory):
    old = dict(app.dependency_overrides)

    def database():
        with gql_session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = database
    try:
        with TestClient(app) as client:
            yield client, {"Authorization": f"Bearer {mint_access_token(gql_data['admin_user'])}"}
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old)


def call(client, headers, patient, doctor, service, target):
    response = client.post("/api/graphql", headers=headers, json={"query": QUERY, "variables": {
        "input": {"patientId": patient, "doctorId": doctor, "serviceIds": [service],
                  "visitDate": target.isoformat(), "discountMode": "repeat"}}})
    assert response.status_code == 200
    body = response.json()
    assert "errors" not in body, body
    return body["data"]["createVisit"]


@pytest.mark.parametrize("case", ["open", "legacy", "wrong_doctor", "future", "outside_window", "inactive", "unknown_currency"])
def test_graphql_repeat_rejects_unverified_evidence_without_creating_visit(
    graph_client, gql_data, gql_session_factory, case
):
    client, headers = graph_client
    with gql_session_factory() as db:
        today = clinic_today(db)
        prior = Visit(patient_id=gql_data["patient"].id, doctor_id=gql_data["doctor"].id,
                      visit_date=today - timedelta(days=1), status="completed", discount_mode="none",
                      repeat_evidence_generation=1, repeat_proof_generation=1,
                      repeat_proof_consultation=True, repeat_proof_doctor_user_id=gql_data["user"].id)
        if case == "open":
            prior.status = "open"
        elif case == "legacy":
            prior.repeat_proof_generation = None
        elif case == "wrong_doctor":
            prior.repeat_proof_doctor_user_id = gql_data["admin_user"].id
        elif case == "future":
            prior.visit_date = today + timedelta(days=1)
        elif case == "inactive":
            db.get(type(gql_data["doctor"]), gql_data["doctor"].id).active = False
        elif case == "unknown_currency":
            db.get(type(gql_data["consult_service"]), gql_data["consult_service"].id).currency = None
        db.add(prior)
        db.commit()
        before = db.query(Visit).filter_by(patient_id=gql_data["patient"].id).count()
    target = today + timedelta(days=30 if case == "outside_window" else 2)
    result = call(client, headers, gql_data["patient"].id, gql_data["doctor"].id,
                  gql_data["consult_service"].id, target)
    assert result["success"] is False
    error = {"unknown_currency": "SERVICE_UNAVAILABLE", "inactive": "DOCTOR_NOT_FOUND"}.get(case, "REPEAT_VISIT_NOT_ELIGIBLE")
    assert result["errors"] == [error]
    with gql_session_factory() as db:
        assert db.query(Visit).filter_by(patient_id=gql_data["patient"].id).count() == before


def test_graphql_repeat_creates_exact_catalog_price_atomically(graph_client, gql_data, gql_session_factory):
    client, headers = graph_client
    with gql_session_factory() as db:
        today = clinic_today(db)
        service = db.get(type(gql_data["consult_service"]), gql_data["consult_service"].id)
        service.price = Decimal("123.45")
        prior = Visit(patient_id=gql_data["patient"].id, doctor_id=gql_data["doctor"].id,
                      visit_date=today - timedelta(days=1), status="closed", discount_mode="none",
                      repeat_evidence_generation=1, repeat_proof_generation=1,
                      repeat_proof_consultation=True, repeat_proof_doctor_user_id=gql_data["user"].id)
        setting = db.query(ClinicSettings).filter_by(key="repeat_visit_discount").first()
        setting_existed = setting is not None
        previous_setting = setting.value if setting is not None else None
        if setting is None:
            setting = ClinicSettings(key="repeat_visit_discount", value=20)
            db.add(setting)
        else:
            setting.value = 20
        db.add(prior)
        db.commit()
    try:
        result = call(client, headers, gql_data["patient"].id, gql_data["doctor"].id,
                      gql_data["consult_service"].id, today + timedelta(days=2))
        assert result["success"] is True, result
        with gql_session_factory() as db:
            visit = db.get(Visit, int(result["visit"]["id"]))
            assert visit.encounter_id is not None
            line = db.query(VisitService).filter_by(visit_id=visit.id).one()
            assert line.price == Decimal("98.76")
            assert line.currency == "UZS"
    finally:
        with gql_session_factory() as db:
            setting = db.query(ClinicSettings).filter_by(key="repeat_visit_discount").one()
            if setting_existed:
                setting.value = previous_setting
            else:
                db.delete(setting)
            db.commit()


def test_graphql_confirmation_missing_visit_preserves_not_found(graph_client):
    client, headers = graph_client
    response = client.post("/api/graphql", headers=headers, json={"query":
        'mutation { updateVisitStatus(id: 2147483000, status: "confirmed") { success errors } }'})
    assert response.status_code == 200
    assert response.json()["data"]["updateVisitStatus"] == {"success": False, "errors": ["VISIT_NOT_FOUND"]}


@pytest.mark.parametrize("currency", ["UZS", None, "KZT"])
def test_normal_graphql_visit_uses_locked_catalog_currency(graph_client, gql_data, gql_session_factory, currency):
    client, headers = graph_client
    with gql_session_factory() as db:
        service = db.get(type(gql_data["service"]), gql_data["service"].id)
        service.currency = currency
        db.commit()
        before = db.query(Visit).filter_by(patient_id=gql_data["patient"].id).count()
    # A second UZS line makes KZT a mixed-currency request.
    response = client.post("/api/graphql", headers=headers, json={"query": QUERY, "variables": {
        "input": {"patientId": gql_data["patient"].id, "serviceIds": [
            gql_data["service"].id, gql_data["consult_service"].id], "discountMode": "none"}}})
    result = response.json()["data"]["createVisit"]
    with gql_session_factory() as db:
        if currency == "UZS":
            assert result["success"] is True, result
            lines = db.query(VisitService).filter_by(visit_id=int(result["visit"]["id"])).all()
            assert len(lines) == 2 and all(line.currency == "UZS" for line in lines)
        else:
            assert result["success"] is False
            assert result["errors"] == ["SERVICE_UNAVAILABLE"]
            assert db.query(Visit).filter_by(patient_id=gql_data["patient"].id).count() == before


def test_normal_graphql_visit_rejects_total_overflow_without_side_effects(graph_client, gql_data, gql_session_factory):
    client, headers = graph_client
    with gql_session_factory() as db:
        db.get(type(gql_data["service"]), gql_data["service"].id).price = Decimal("9999999999.99")
        db.get(type(gql_data["consult_service"]), gql_data["consult_service"].id).price = Decimal("0.01")
        db.commit()
        before = db.query(Visit).filter_by(patient_id=gql_data["patient"].id).count()
    response = client.post("/api/graphql", headers=headers, json={"query": QUERY, "variables": {
        "input": {"patientId": gql_data["patient"].id, "serviceIds": [
            gql_data["service"].id, gql_data["consult_service"].id], "discountMode": "none"}}})
    result = response.json()["data"]["createVisit"]
    assert result["success"] is False
    assert result["errors"] == ["SERVICE_UNAVAILABLE"]
    with gql_session_factory() as db:
        assert db.query(Visit).filter_by(patient_id=gql_data["patient"].id).count() == before


@pytest.mark.parametrize("mode", ["benefit", "all_free"])
def test_graphql_review_modes_never_create_unapproved_discount(graph_client, gql_data, gql_session_factory, mode):
    client, headers = graph_client
    with gql_session_factory() as db:
        before = db.query(Visit).filter_by(patient_id=gql_data["patient"].id).count()
    response = client.post("/api/graphql", headers=headers, json={"query": QUERY, "variables": {
        "input": {"patientId": gql_data["patient"].id, "doctorId": gql_data["doctor"].id,
                  "serviceIds": [gql_data["consult_service"].id], "discountMode": mode}}})
    result = response.json()["data"]["createVisit"]
    assert result["success"] is False
    assert result["errors"] == ["REVIEW_WORKFLOW_REQUIRED"]
    with gql_session_factory() as db:
        assert db.query(Visit).filter_by(patient_id=gql_data["patient"].id).count() == before
