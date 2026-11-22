"""Pure unit coverage for the final parent-lock check of issued QR tokens."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, QueueResource
from app.models.queue_profile import QueueProfile
from app.services import queue_profile_availability
from app.services.queue_profile_availability import resolve_queue_profile_availability
from app.services.queue_service import QueueBusinessService


def _session(profiles, doctor):
    """Supply query results without opening a connection or writing fixtures."""
    db = Mock(spec=Session)
    profile_query = Mock()
    profile_query.all.return_value = profiles
    doctor_query = Mock()
    doctor_query.filter.return_value.first.return_value = doctor
    doctor_specialty_query = Mock()
    doctor_specialty_query.join.return_value.filter.return_value.distinct.return_value.all.return_value = (
        [(doctor.specialty,)] if doctor is not None else []
    )
    resource_tag_query = Mock()
    resource_tag_query.filter.return_value.all.return_value = []
    queue_tag_query = Mock()
    queue_tag_query.filter.return_value.order_by.return_value.all.return_value = []
    active_queue_query = Mock()
    active_queue_query.filter.return_value.filter.return_value.order_by.return_value.all.return_value = (
        []
    )

    def query(*models):
        if len(models) == 1 and models[0] is QueueProfile:
            return profile_query
        if len(models) == 1 and models[0] is Doctor:
            return doctor_query
        if len(models) == 1 and models[0] is Doctor.specialty:
            return doctor_specialty_query
        if len(models) == 1 and models[0] is QueueResource.queue_tag:
            return resource_tag_query
        if len(models) == 2 and models[0] is DailyQueue.queue_tag:
            return queue_tag_query
        if len(models) == 1 and models[0] is DailyQueue:
            return active_queue_query
        raise AssertionError(f"Unexpected query model: {models}")

    db.query.side_effect = query
    return db


def _availability_loader(monkeypatch, *, parent_active):
    parent = SimpleNamespace(key="synthetic-parent", active=parent_active)
    loader = Mock(
        side_effect=lambda _db, profiles, **_kwargs: {
            profile: resolve_queue_profile_availability(profile, {parent.key: parent})
            for profile in profiles
        }
    )
    monkeypatch.setattr(
        queue_profile_availability, "load_queue_profile_availability", loader
    )
    return loader


def _profile():
    return QueueProfile(
        key="synthetic-doctor-profile",
        queue_tags=["synthetic-doctor-profile"],
        department_key="synthetic-parent",
        is_active=True,
        show_on_qr_page=True,
    )


@pytest.mark.parametrize(
    "queue_tag", [None, "synthetic-unmatched"], ids=["null", "unmatched"]
)
@pytest.mark.parametrize(
    "parent_active", [True, False], ids=["parent-on", "parent-off"]
)
def test_doctor_token_without_tag_profile_rechecks_doctor_parent_under_lock(
    monkeypatch, queue_tag, parent_active
):
    profile = _profile()
    doctor = Doctor(id=73, specialty=profile.key)
    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor.id,
        queue_resource_id=None,
        queue_tag=queue_tag,
    )
    db = _session([profile], doctor)
    loader = _availability_loader(monkeypatch, parent_active=parent_active)

    result = QueueBusinessService._queue_profiles_are_bookable_under_parent_locks(
        db, queue
    )

    assert result is parent_active
    loader.assert_called_once_with(db, [profile], lock_parent_rows=True)
    db.query.assert_any_call(Doctor)
    assert queue.queue_tag == queue_tag
    assert queue.specialist_id == doctor.id
    assert queue.queue_resource_id is None


@pytest.mark.parametrize("resource_owned", [False, True], ids=["doctor", "resource"])
def test_tag_matched_token_rechecks_only_tag_profiles(monkeypatch, resource_owned):
    profile = _profile()
    queue = DailyQueue(
        specialist_id=None if resource_owned else 73,
        queue_resource_id=81 if resource_owned else None,
        queue_tag=profile.key,
    )
    db = _session([profile], Doctor(id=73, specialty="synthetic-other"))
    loader = _availability_loader(monkeypatch, parent_active=False)

    assert not QueueBusinessService._queue_profiles_are_bookable_under_parent_locks(
        db, queue
    )

    loader.assert_called_once_with(db, [profile], lock_parent_rows=True)
    assert all(call.args != (Doctor,) for call in db.query.call_args_list)


@pytest.mark.parametrize(
    "queue_tag", [None, "synthetic-unmatched"], ids=["null", "unmatched"]
)
def test_resource_token_without_tag_profile_keeps_legacy_behavior(
    monkeypatch, queue_tag
):
    profile = _profile()
    db = _session([profile], Doctor(id=73, specialty=profile.key))
    loader = _availability_loader(monkeypatch, parent_active=False)
    queue = DailyQueue(specialist_id=None, queue_resource_id=81, queue_tag=queue_tag)

    assert QueueBusinessService._queue_profiles_are_bookable_under_parent_locks(
        db, queue
    )

    loader.assert_not_called()
    assert all(call.args != (Doctor,) for call in db.query.call_args_list)


@pytest.mark.parametrize(
    "doctor_exists", [True, False], ids=["unconfigured", "missing"]
)
def test_doctor_token_without_configured_profile_keeps_legacy_behavior(
    monkeypatch, doctor_exists
):
    doctor = (
        Doctor(id=73, specialty="synthetic-unconfigured") if doctor_exists else None
    )
    db = _session([_profile()], doctor)
    loader = _availability_loader(monkeypatch, parent_active=False)
    queue = DailyQueue(specialist_id=73, queue_resource_id=None, queue_tag=None)

    assert QueueBusinessService._queue_profiles_are_bookable_under_parent_locks(
        db, queue
    )

    loader.assert_not_called()
