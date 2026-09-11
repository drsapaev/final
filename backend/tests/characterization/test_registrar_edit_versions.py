"""A submitted queue version is an exact server token, not a client clock."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from app.models.online_queue import OnlineQueueEntry
from app.services.registrar_edit_delta_service import RegistrarEditDeltaService
from tests.characterization.test_registrar_edit_delta_characterization import (
    _create_entry,
    _create_queue,
    _create_service,
)


@pytest.fixture
def versioned_entry(db_session, test_patient, test_doctor):
    service = _create_service(
        db_session,
        code="SYNTH-V",
        name="SYNTHETIC-Versioned service",
        queue_tag="laboratory_general",
    )
    queue = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general"
    )
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service
    )
    entry.updated_at = datetime(2026, 1, 1, 10, 0, 0, 123456, tzinfo=UTC)
    db_session.commit()
    db_session.refresh(entry)
    return entry


@pytest.mark.parametrize(
    "offset",
    [timedelta(microseconds=1), timedelta(milliseconds=500), timedelta(seconds=1)],
)
def test_subsecond_stale_version_is_rejected(db_session, versioned_entry, offset):
    token = (versioned_entry.updated_at - offset).isoformat()
    with pytest.raises(ValueError, match="изменена другим пользователем"):
        RegistrarEditDeltaService(db_session)._assert_entries_not_concurrently_modified(
            {versioned_entry.id: token}
        )


@pytest.mark.parametrize(
    "token", ["", "not-a-timestamp", "2026-01-01", "2026-01-01T10:00:00+99:00"]
)
def test_invalid_version_cannot_bypass_guard(db_session, versioned_entry, token):
    with pytest.raises(ValueError):
        RegistrarEditDeltaService(db_session)._assert_entries_not_concurrently_modified(
            {versioned_entry.id: token}
        )


def test_equivalent_timezone_keeps_exact_server_precision(db_session, versioned_entry):
    actual = versioned_entry.updated_at.replace(tzinfo=UTC)
    token = actual.astimezone(timezone(timedelta(hours=5))).isoformat()
    RegistrarEditDeltaService(db_session)._assert_entries_not_concurrently_modified(
        {versioned_entry.id: token}
    )


def test_guard_refreshes_already_loaded_entry(db_session, versioned_entry):
    old = versioned_entry.updated_at
    # Simulate a database update while the session still holds an older object.
    db_session.execute(
        update(OnlineQueueEntry)
        .where(OnlineQueueEntry.id == versioned_entry.id)
        .values(updated_at=old + timedelta(seconds=2))
        .execution_options(synchronize_session=False)
    )
    assert versioned_entry.updated_at == old
    with pytest.raises(ValueError, match="изменена другим пользователем"):
        RegistrarEditDeltaService(db_session)._assert_entries_not_concurrently_modified(
            {versioned_entry.id: old.isoformat()}
        )


def test_unverifiable_version_is_rejected(db_session, versioned_entry):
    token = versioned_entry.updated_at.isoformat()
    versioned_entry.updated_at = None
    db_session.commit()
    with pytest.raises(ValueError):
        RegistrarEditDeltaService(db_session)._assert_entries_not_concurrently_modified(
            {versioned_entry.id: token}
        )


@pytest.mark.parametrize("invalid", [False, True])
def test_rejected_edit_does_not_mutate_patient_or_services(
    client, db_session, registrar_auth_headers, test_patient, versioned_entry, invalid
):
    original_name = test_patient.full_name
    original_services = versioned_entry.services
    token = (
        "invalid-version"
        if invalid
        else (versioned_entry.updated_at - timedelta(milliseconds=500)).isoformat()
    )
    response = client.post(
        "/api/v1/registrar/cart/edit-delta",
        headers=registrar_auth_headers,
        json={
            "patient_id": test_patient.id,
            "target_date": date.today().isoformat(),
            "services": [
                {"service_id": versioned_entry.services[0]["id"], "quantity": 2}
            ],
            "existing_queue_entry_ids": [versioned_entry.id],
            "patient_data": {"full_name": "SYNTHETIC-Rejected Edit"},
            "expected_entry_updated_at": {str(versioned_entry.id): token},
        },
    )
    assert response.status_code == 400, response.text
    db_session.refresh(test_patient)
    db_session.refresh(versioned_entry)
    assert test_patient.full_name == original_name
    assert versioned_entry.services == original_services
