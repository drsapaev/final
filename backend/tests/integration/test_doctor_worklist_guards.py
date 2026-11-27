from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import AsyncMock, Mock

from sqlalchemy import event

from app.crud.clinic import clinic_today
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.services.display_websocket import get_display_manager

LOGIN = "/api/v1/authentication/login"
TODAY_URL = "/api/v1/doctor/general/queue/today"


def _make_host_date_behind(clinic_day: date):
    """A stand-in for datetime.date whose clock runs BEHIND the clinic
    (mirrors a UTC backend while the clinic in Asia/Tashkent is already
    on the next day)."""

    class _HostDateBehind(date):
        @classmethod
        def today(cls):
            return cls.fromordinal(clinic_day.toordinal() - 2)

    return _HostDateBehind


def _make_general_doctor(db_session, test_doctor_user):
    doctor = Doctor(
        user_id=test_doctor_user.id,
        specialty="general",
        active=True,
        cabinet="101",
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _login(client, test_doctor_user):
    login_response = client.post(
        LOGIN,
        json={"username": test_doctor_user.username, "password": "doctor123"},
    )
    assert login_response.status_code == 200
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


def _make_queue_with_entry(db_session, doctor, patient, day, active):
    queue = DailyQueue(
        day=day,
        specialist_id=doctor.id,
        queue_tag="general",
        active=active,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=1,
        patient_id=patient.id,
        patient_name=patient.short_name(),
        phone=patient.phone,
        source="desk",
        status="waiting",
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return queue, entry


class TestDoctorWorklistGuards:
    def test_doctor_queue_today_uses_clinic_today_not_host_date(
        self,
        client,
        db_session,
        monkeypatch,
        test_doctor_user,
        test_patient,
    ):
        """DOCWORKLIST-BE-001 (audit 3892 group 24): get_doctor_queue_today
        must resolve the day via clinic_today — the queue SSOT — instead of
        the host clock: a UTC backend behind the clinic read the wrong day
        and answered queue_exists=false while patients were waiting."""
        doctor = _make_general_doctor(db_session, test_doctor_user)
        clinic_day = clinic_today(db_session)
        _queue, entry = _make_queue_with_entry(
            db_session, doctor, test_patient, clinic_day, active=True
        )

        monkeypatch.setattr(
            "app.api.v1.endpoints.doctor_integration._queue_ops.date",
            _make_host_date_behind(clinic_day),
        )

        headers = _login(client, test_doctor_user)
        response = client.get(TODAY_URL, headers=headers)

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["queue_exists"] is True, payload
        assert payload["date"] == clinic_day.isoformat(), payload
        assert any(item["id"] == entry.id for item in payload["entries"]), payload

    def test_inactive_queue_keeps_history_without_call_actions(
        self,
        client,
        db_session,
        test_doctor_user,
        test_patient,
    ):
        """DOCWORKLIST-BE-002 (audit 3892 group 24): the entries projection
        must not publish an operational next-call marker for an INACTIVE
        queue — viewing/history stays readable (owner-policy), operational
        affordances fail closed."""
        doctor = _make_general_doctor(db_session, test_doctor_user)
        clinic_day = clinic_today(db_session)
        _queue, entry = _make_queue_with_entry(
            db_session, doctor, test_patient, clinic_day, active=False
        )

        headers = _login(client, test_doctor_user)
        response = client.get(TODAY_URL, headers=headers)

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["queue_exists"] is True, payload
        row = next(item for item in payload["entries"] if item["id"] == entry.id)
        assert row["can_call"] is False
        assert "call" not in row["available_actions"]
        assert payload["next_call_entry_id"] is None, payload
        assert payload["can_call_next"] is False, payload

    def test_call_patient_rejects_inactive_queue(
        self,
        client,
        db_session,
        test_doctor_user,
        test_patient,
        monkeypatch,
    ):
        """DOCWORKLIST-BE-002 (audit 3892 group 24): doctor call_patient
        must fail closed for an INACTIVE queue — previously it validated
        specialty and entry status only, so inactive same-day queues stayed
        operable."""
        doctor = _make_general_doctor(db_session, test_doctor_user)
        clinic_day = clinic_today(db_session)
        _queue, entry = _make_queue_with_entry(
            db_session, doctor, test_patient, clinic_day, active=False
        )
        sender = AsyncMock()
        monkeypatch.setattr(get_display_manager(), "broadcast_patient_call_data", sender)

        headers = _login(client, test_doctor_user)
        response = client.post(
            f"/api/v1/doctor/queue/{entry.id}/call", headers=headers
        )

        assert response.status_code == 409, response.text
        db_session.refresh(entry)
        assert entry.status == "waiting", entry.status
        assert entry.called_at is None
        sender.assert_not_awaited()

    def test_call_patient_allows_active_queue(
        self,
        client,
        db_session,
        test_doctor_user,
        test_patient,
        monkeypatch,
    ):
        doctor = _make_general_doctor(db_session, test_doctor_user)
        clinic_day = clinic_today(db_session)
        _queue, entry = _make_queue_with_entry(
            db_session, doctor, test_patient, clinic_day, active=True
        )

        headers = _login(client, test_doctor_user)
        worklist = client.get(TODAY_URL, headers=headers)
        assert worklist.status_code == 200, worklist.text
        payload = worklist.json()
        row = next(item for item in payload["entries"] if item["id"] == entry.id)
        assert row["can_call"] is True
        assert "call" in row["available_actions"]
        assert payload["next_call_entry_id"] == entry.id

        manager = get_display_manager()
        boards = ["synthetic-hall", "synthetic-mask-names"]
        name_format = Mock(return_value="none")
        monkeypatch.setattr(manager, "_resolve_untargeted_board_ids", Mock(return_value=boards))
        monkeypatch.setattr(manager, "_resolve_name_format", name_format)
        effects = []

        def record_commit(session):
            effects.append("commit")

        async def record_send(message, board_ids):
            assert asyncio.get_running_loop().is_running()
            effects.append("send")
            return dict.fromkeys(board_ids, "published_only")

        sender = AsyncMock(side_effect=record_send)
        monkeypatch.setattr(manager, "broadcast_patient_call_data", sender)
        event.listen(db_session, "after_commit", record_commit)
        try:
            response = client.post(f"/api/v1/doctor/queue/{entry.id}/call", headers=headers)
        finally:
            event.remove(db_session, "after_commit", record_commit)

        assert response.status_code == 200, response.text
        db_session.refresh(entry)
        assert entry.status == "called", entry.status
        assert entry.called_by_user_id == test_doctor_user.id
        assert effects == ["commit", "send"]
        assert response.json()["display_delivery"] == "published_only"
        name_format.assert_called_once_with(boards)
        assert sender.await_count == 1
        message, = sender.await_args.args
        assert sender.await_args.kwargs == {"board_ids": boards}
        assert message["data"]["queue_entry_id"] == entry.id
        assert message["data"]["called_at"] == response.json()["entry"]["called_at"]
        assert message["data"]["called_at"] == entry.called_at.isoformat()
        assert message["data"]["patient_name"] == "Пациент"
        assert message["data"]["cabinet"] == doctor.cabinet
