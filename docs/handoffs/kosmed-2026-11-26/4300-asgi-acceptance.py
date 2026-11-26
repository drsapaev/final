import os

import pytest


@pytest.fixture(scope="session")
def test_db():
    from app.db.session import engine
    from app.db.base_class import Base
    from app.services.medical_specialty_seed import seed_medical_specialties

    assert engine.url.get_backend_name() == "postgresql"
    assert engine.url.host == "127.0.0.1"
    assert engine.url.database == "clinic_test_nurse4300"
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        seed_medical_specialties(conn)
    yield engine
    engine.dispose()

from tests.integration.test_docvisit_pricing_integrity import (
    _add, _create_doctor, _create_user, _login_headers
)
from tests.unit.test_nurse_serving_service import (
    _assignment, _entry, _patient, _resource, _service, _station_queue, _visit, _visit_service
)
from app.models.online_queue import OnlineQueueEntry

def test_late_catalog_order_after_real_nurse_serving(client, db_session):
    db = db_session
    doctor_user = _create_user(db, role="Doctor", label="synthetic_late_doctor")
    doctor = _create_doctor(db, doctor_user, specialty="cardiology")
    nurse = _create_user(db, role="Nurse", label="synthetic_late_nurse")
    station = _resource(db, "synthetic_late_accept")
    control = _resource(db, "synthetic_late_control")
    _assignment(db, nurse, station)
    _assignment(db, nurse, control)
    queue = _station_queue(db, station)
    _station_queue(db, control)
    patient = _patient(db, "SYNTHETIC Late Acceptance")
    visit = _visit(db, patient, department="cardiology")
    visit.doctor_id = doctor.id
    db.commit()
    entry = _entry(db, queue, 1, patient=patient, visit=visit)
    initial = _service(db, "SYN-LATE-INITIAL", queue_tag=station.queue_tag)
    late = _service(db, "SYN-LATE-ADDED", queue_tag=station.queue_tag)
    initial.price = late.price = 50000
    initial.duration_minutes = late.duration_minutes = 15
    db.commit()
    assigned = _visit_service(db, visit, initial)
    nurse_auth = _login_headers(client, nurse)
    doctor_auth = _login_headers(client, doctor_user)
    prefix = "/api/v1/nurse/serving"
    station_url = f"{prefix}/queue-resources/{station.id}"
    def post(url, expected=200, **kwargs):
        r = client.post(url, headers=nurse_auth, **kwargs)
        assert r.status_code == expected, r.text
        return r.json()
    def get(url):
        r = client.get(url, headers=nurse_auth)
        assert r.status_code == 200, r.text
        return r.json()
    assert post(f"{station_url}/call-next")["entry"]["id"] == entry.id
    post(f"{station_url}/entries/{entry.id}/start")
    started = post(
        f"{station_url}/executions", 201,
        json={"queue_entry_id": entry.id, "visit_service_id": assigned.id},
    )
    assert post(f"{prefix}/executions/{started['id']}/complete")["entry_served"] is True
    assert get(f"{station_url}/entries")["late_pending"] == []
    result = _add(client, doctor_auth, visit_id=visit.id, service_id=late.id)
    assert result.status_code == 200, result.text
    new_service_id = result.json()["visit_service"]["id"]
    items = get(f"{station_url}/entries")["late_pending"]
    assert len(items) == 1
    assert items[0]["id"] == entry.id
    assert items[0]["visit_id"] == visit.id
    assert items[0]["status"] == "served"
    assert [x["visit_service_id"] for x in items[0]["services"] if x["pending"]] == [new_service_id]
    assert get(f"{prefix}/queue-resources/{control.id}/entries")["late_pending"] == []
    db.expire_all()
    assert db.get(OnlineQueueEntry, entry.id).status == "served"
    assert db.query(OnlineQueueEntry).filter_by(visit_id=visit.id).count() == 1
