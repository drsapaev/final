"""DOCSCHED-BE-001..005 (audit #3892, group 18) — schedule-next integrity.

Fail-first coverage for the doctor schedule-next visit-creation plane:

* **DOCSCHED-BE-001 (P1/P2)** — repeat POST /doctor/visits/schedule-next
  created an additional ``pending_confirmation`` visit + confirmation
  token on every retry (no operation-level idempotency). An identical
  replay inside the short dedup window must return the ORIGINAL visit
  (same visit_id/token, ``idempotent_replay: true``) without
  re-dispatching the patient invitation; a changed intent (or a replay
  after the window lapses) still creates a new visit.
* **DOCSCHED-BE-002 (P1)** — payment and confirmation track the actual
  pricing decision. The All Free approval contract is tested separately in
  ``test_doctor_all_free_workflow.py``.
* **DOCSCHED-BE-003 (P2)** — past-date validation used the HOST's
  ``date.today()``; between 19:00–24:00 UTC the clinic (Asia/Tashkent)
  calendar day has already advanced and a past clinic-local date was
  accepted. Validation now uses the ``clinic_today`` SSOT.
* **DOCSCHED-BE-004 (P1/P2)** — Admin without a Doctor profile created
  a visit with ``doctor_id = current_user.id`` — a ``users.id`` stored
  in a ``doctors.id`` FK (FK error on PostgreSQL; silent attribution to
  an UNRELATED doctor on id collision). Non-doctor principals now
  create an unowned visit (``doctor_id=None``) the queue plane already
  treats fail-closed (D-08).
* **DOCSCHED-BE-005 (P2)** — an arbitrary ``visit_time`` string
  (``'29:99'``, ``'notime'``) was accepted into a pending confirmation
  visit. The field now enforces canonical zero-padded ``HH:MM``.

Schedule-next service financial inputs (the DOCVISIT-BE-002 root risk
through its second entrypoint): ``quantity``/``custom_price`` are
validated before persistence, and an explicit ``custom_price=0`` is an
intended free override, not a catalogue fallback.
"""

from __future__ import annotations

import json
import math
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.clinic import ClinicSettings, Doctor
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from tests.conftest import mint_access_token
from tests.integration.doctor_schedule_fixtures import (
    keyed_schedule_headers,
    mock_invitations,  # noqa: F401
    observe_invitation_staging,
)

pytestmark = pytest.mark.usefixtures("mock_invitations")


def _clinic_today(db_session) -> date:
    """SSOT: день КЛИНИКИ (Asia/Tashkent), а не host-UTC дата."""
    from app.crud.clinic import clinic_today

    return clinic_today(db_session)


def _unique_suffix() -> str:
    return uuid4().hex[:10]


def _prior_context_visit(db_session, *, patient: Patient, doctor: Doctor) -> Visit:
    """Врач расписывает СВОЕГО пациента: pre-existing visit создаёт
    patient↔doctor context для schedule-next (как в e2e-суите)."""
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=_clinic_today(db_session),
        visit_time="09:00",
        status="open",
        discount_mode="none",
        source="desk",
    )
    db_session.add(visit)
    db_session.commit()
    return visit


def _make_service(
    db_session, *, price: float = 150000.0, is_consultation: bool = False
) -> Service:
    suffix = _unique_suffix()
    service = Service(
        code=f"DSCH{suffix[:6].upper()}",
        name=f"Услуга {suffix}",
        price=price,
        duration_minutes=30,
        active=True,
        requires_doctor=True,
        queue_tag="cardiology_common",
        is_consultation=is_consultation,
        allow_doctor_price_override=False,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def _make_patient(db_session) -> Patient:
    suffix = _unique_suffix()
    patient = Patient(
        first_name="Иван",
        last_name=f"Расписание{suffix[:4].upper()}",
        phone=f"+99890{suffix[:7]}",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _schedule_payload(
    patient: Patient, service: Service, *, visit_date: date, **overrides
) -> dict:
    payload = {
        "patient_id": patient.id,
        "services": [{"service_id": service.id, "quantity": 1}],
        "visit_date": visit_date.isoformat(),
        "visit_time": "10:00",
        "discount_mode": "none",
        "all_free": False,
        "confirmation_channel": "phone",
    }
    payload.update(overrides)
    return payload


def _pending_visits(db_session, *, patient_id: int) -> list[Visit]:
    return (
        db_session.query(Visit)
        .filter(
            Visit.patient_id == patient_id,
            Visit.status == "pending_confirmation",
        )
        .all()
    )


@pytest.mark.integration
@pytest.mark.confirmation
class TestDOCSCHEDBE001ScheduleNextReplayIdempotency:
    """DOCSCHED-BE-001: повторный идентичный schedule-next — это replay,
    не второй визит и не второй токен подтверждения."""

    def _spy_invitation(self, monkeypatch) -> list[tuple[int, str]]:
        return observe_invitation_staging(monkeypatch)

    def test_replayed_identical_request_returns_original_visit(
        self,
        client,
        db_session,
        cardio_auth_headers,
        test_doctor,
        test_service,
        monkeypatch,
    ):
        patient = _make_patient(db_session)
        _prior_context_visit(
            db_session, patient=patient, doctor=test_doctor
        )
        calls = self._spy_invitation(monkeypatch)
        visit_date = _clinic_today(db_session) + timedelta(days=1)
        payload = _schedule_payload(patient, test_service, visit_date=visit_date)
        schedule_headers = keyed_schedule_headers(cardio_auth_headers)

        first = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=payload,
            headers=schedule_headers,
        )
        assert first.status_code == 200, first.text
        first_data = first.json()

        second = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=payload,
            headers=schedule_headers,
        )
        assert second.status_code == 200, second.text
        second_data = second.json()

        # Один визит, один токен: replay возвращает исходную операцию.
        assert second_data["visit_id"] == first_data["visit_id"]
        assert (
            second_data["confirmation"]["token"]
            == first_data["confirmation"]["token"]
        )
        assert second_data.get("idempotent_replay") is True
        assert first_data.get("idempotent_replay") is False

        pending = _pending_visits(db_session, patient_id=patient.id)
        assert len(pending) == 1, "повторный запрос создал второй визит"

        assert len(calls) == 1, "replay повторно подготовил приглашение"

    def test_new_visit_at_same_time_requires_an_explicit_new_intent(
        self,
        client,
        db_session,
        cardio_auth_headers,
        test_doctor,
        test_service,
    ):
        """An explicitly new request can book the same schedule slot."""
        patient = _make_patient(db_session)
        _prior_context_visit(db_session, patient=patient, doctor=test_doctor)
        visit_date = _clinic_today(db_session) + timedelta(days=1)
        payload = _schedule_payload(patient, test_service, visit_date=visit_date)

        first = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=payload,
            headers=cardio_auth_headers,
        )
        second = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=payload,
            headers={
                **cardio_auth_headers,
                "Idempotency-Key": f"synthetic-{uuid4()}",
                "Idempotency-Intent": "new",
            },
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["visit_id"] != first.json()["visit_id"]
        assert second.json().get("idempotent_replay") is False
        assert len(_pending_visits(db_session, patient_id=patient.id)) == 2

    def test_changed_intent_is_not_a_replay(
        self,
        client,
        db_session,
        cardio_auth_headers,
        test_doctor,
        test_service,
    ):
        """Изменившееся время визита — другой intent: второй визит создаётся."""
        patient = _make_patient(db_session)
        _prior_context_visit(db_session, patient=patient, doctor=test_doctor)
        visit_date = _clinic_today(db_session) + timedelta(days=1)

        first = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=_schedule_payload(patient, test_service, visit_date=visit_date),
            headers=cardio_auth_headers,
        )
        second = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=_schedule_payload(
                patient, test_service, visit_date=visit_date, visit_time="11:30"
            ),
            headers={
                **cardio_auth_headers,
                "Idempotency-Key": f"synthetic-{uuid4()}",
                "Idempotency-Intent": "new",
            },
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["visit_id"] != first.json()["visit_id"]
        assert second.json().get("idempotent_replay") is False
        assert len(_pending_visits(db_session, patient_id=patient.id)) == 2

    def test_changed_confirmation_channel_is_not_a_replay(
        self,
        client,
        db_session,
        cardio_auth_headers,
        test_doctor,
        test_service,
        monkeypatch,
    ):
        """An explicit new intent stores and stages its own confirmation channel."""
        patient = _make_patient(db_session)
        _prior_context_visit(db_session, patient=patient, doctor=test_doctor)
        calls = self._spy_invitation(monkeypatch)
        visit_date = _clinic_today(db_session) + timedelta(days=1)
        first_headers = keyed_schedule_headers(cardio_auth_headers)

        first = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=_schedule_payload(
                patient, test_service, visit_date=visit_date, confirmation_channel="phone"
            ),
            headers=first_headers,
        )
        second = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=_schedule_payload(
                patient, test_service, visit_date=visit_date, confirmation_channel="telegram"
            ),
            headers={
                **cardio_auth_headers,
                "Idempotency-Key": f"synthetic-{uuid4()}",
                "Idempotency-Intent": "new",
            },
        )
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text

        # Изменённый канал — не replay: создаётся второй визит.
        first_data = first.json()
        second_data = second.json()
        assert second_data.get("idempotent_replay") is False
        assert second_data["visit_id"] != first_data["visit_id"]
        assert len(_pending_visits(db_session, patient_id=patient.id)) == 2

        second_visit = (
            db_session.query(Visit)
            .filter(Visit.id == second_data["visit_id"])
            .one()
        )
        assert second_visit.confirmation_channel == "telegram"
        assert second_data["confirmation"]["channel"] == "telegram"
        assert ("telegram" in [channel for _, channel in calls]), (
            "приглашение не подготовлено для изменённого канала"
        )
        assert len(calls) == 2, "второй intent должен подготовить своё приглашение"

        # Контроль: идентичный повтор ИСХОДНОГО запроса по-прежнему replay
        # исходного phone-визита (дедуп по полному intent'у не сломан).
        third = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=_schedule_payload(
                patient, test_service, visit_date=visit_date, confirmation_channel="phone"
            ),
            headers=first_headers,
        )
        assert third.status_code == 200
        third_data = third.json()
        assert third_data.get("idempotent_replay") is True
        assert third_data["visit_id"] == first_data["visit_id"]
        assert third_data["confirmation"]["channel"] == "phone"
        assert len(calls) == 2, "replay повторно подготовил приглашение"

    def test_replayed_replay_reports_persisted_channel_not_requested(
        self,
        client,
        db_session,
        cardio_auth_headers,
        test_doctor,
        test_service,
    ):
        """RETRO-3960-01 (контракт): канал replay-ответа всегда совпадает с
        каналом сохранённого визита (same-channel replay инвариант)."""
        patient = _make_patient(db_session)
        _prior_context_visit(db_session, patient=patient, doctor=test_doctor)
        visit_date = _clinic_today(db_session) + timedelta(days=1)
        payload = _schedule_payload(
            patient, test_service, visit_date=visit_date, confirmation_channel="pwa"
        )
        schedule_headers = keyed_schedule_headers(cardio_auth_headers)

        first = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=payload,
            headers=schedule_headers,
        )
        second = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=payload,
            headers=schedule_headers,
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json().get("idempotent_replay") is True
        second_visit = (
            db_session.query(Visit)
            .filter(Visit.id == second.json()["visit_id"])
            .one()
        )
        assert second_visit.confirmation_channel == "pwa"
        assert second.json()["confirmation"]["channel"] == second_visit.confirmation_channel


@pytest.mark.integration
@pytest.mark.confirmation
class TestDOCSCHEDBE002RepeatCanonicalPricing:
    """The repeat rate reflects current policy and completed consultations."""

    def _schedule(
        self, client, headers, patient, service, visit_date, **overrides
    ):
        response = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=_schedule_payload(
                patient, service, visit_date=visit_date, **overrides
            ),
            headers=headers,
        )
        assert response.status_code == 200, response.text
        visit_id = response.json()["visit_id"]
        return response.json(), visit_id

    def test_repeat_discount_zeroes_consultation_only_when_configured(
        self, client, db_session, cardio_auth_headers, test_doctor, test_service
    ):
        """A completed consultation and a configured 100% discount are required."""
        patient = _make_patient(db_session)
        prior = _prior_context_visit(db_session, patient=patient, doctor=test_doctor)
        prior.status = "completed"
        test_service.is_consultation = True
        db_session.add(VisitService(
            visit_id=prior.id, service_id=test_service.id, name=test_service.name,
            qty=1, price=test_service.price,
        ))
        # Metadata-only test DB has no migration triggers; represent the
        # verified synthetic completion explicitly in this focused fixture.
        prior.repeat_proof_generation = prior.repeat_evidence_generation
        prior.repeat_proof_consultation = True
        prior.repeat_proof_doctor_user_id = test_doctor.user_id
        setting = db_session.query(ClinicSettings).filter_by(key="repeat_visit_discount").first()
        if setting is None:
            setting = ClinicSettings(key="repeat_visit_discount", value=100)
            db_session.add(setting)
        else:
            setting.value = 100
        db_session.commit()
        paid_service = _make_service(db_session, price=150000.0)
        visit_date = _clinic_today(db_session) + timedelta(days=1)

        data, visit_id = self._schedule(
            client,
            cardio_auth_headers,
            patient,
            paid_service,
            visit_date,
            services=[
                {"service_id": test_service.id, "quantity": 1},
                {"service_id": paid_service.id, "quantity": 1},
            ],
            discount_mode="repeat",
            all_free=False,
        )

        visit = db_session.get(Visit, visit_id)
        assert visit.discount_mode == "repeat"
        prices = {
            line.service_id: line.price
            for line in db_session.query(VisitService)
            .filter(VisitService.visit_id == visit_id)
            .all()
        }
        assert prices[test_service.id] == 0
        assert prices[paid_service.id] == 150000.0
        assert data["confirmation"]["total_amount"] == 150000.0


@pytest.mark.integration
@pytest.mark.confirmation
@pytest.mark.parametrize("all_free", [False, True])
def test_schedule_next_routes_encounter_benefits_to_registration(
    client, db_session, cardio_auth_headers, test_doctor, all_free
):
    patient = _make_patient(db_session)
    prior_visit = _prior_context_visit(db_session, patient=patient, doctor=test_doctor)
    consultation = _make_service(db_session, is_consultation=True)
    payload = _schedule_payload(
        patient,
        consultation,
        visit_date=_clinic_today(db_session) + timedelta(days=1),
        discount_mode="benefit",
        all_free=all_free,
    )

    response = client.post(
        "/api/v1/doctor/visits/schedule-next", json=payload, headers=cardio_auth_headers
    )

    assert response.status_code == 409, response.text
    assert "регистра" in response.json()["detail"]
    visit_ids = db_session.query(Visit.id).filter(Visit.patient_id == patient.id).all()
    assert visit_ids == [(prior_visit.id,)]


@pytest.mark.integration
@pytest.mark.confirmation
class TestDOCSCHEDBE003ClinicLocalDateValidation:
    """DOCSCHED-BE-003: прошедшая дата определяется по календарю КЛИНИКИ."""

    def test_past_clinic_day_rejected_even_when_host_date_agrees(
        self,
        client,
        db_session,
        cardio_auth_headers,
        test_doctor,
        test_service,
        monkeypatch,
    ):
        """UTC-хост ещё «вчера не было», а клиника уже в новом дне:
        host-проверка пропускала прошедшую для клиники дату."""
        from app.api.v1.endpoints.doctor_integration import _visits as visits_mod

        clinic_day = date.today() + timedelta(days=1)
        monkeypatch.setattr(
            visits_mod, "clinic_today", lambda db: clinic_day
        )

        patient = _make_patient(db_session)
        _prior_context_visit(db_session, patient=patient, doctor=test_doctor)

        # host-дата (date.today()) проходит host-проверку, но для клиники
        # это уже прошедший день.
        response = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=_schedule_payload(
                patient, test_service, visit_date=date.today()
            ),
            headers=cardio_auth_headers,
        )
        assert response.status_code == 400, (
            "прошедшая по календарю клиники дата принята host-проверкой"
        )
        assert _pending_visits(db_session, patient_id=patient.id) == []

    def test_clinic_today_boundary_accepted(
        self,
        client,
        db_session,
        cardio_auth_headers,
        test_doctor,
        test_service,
        monkeypatch,
    ):
        from app.api.v1.endpoints.doctor_integration import _visits as visits_mod

        clinic_day = date.today() + timedelta(days=1)
        monkeypatch.setattr(
            visits_mod, "clinic_today", lambda db: clinic_day
        )

        patient = _make_patient(db_session)
        _prior_context_visit(db_session, patient=patient, doctor=test_doctor)

        response = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=_schedule_payload(patient, test_service, visit_date=clinic_day),
            headers=cardio_auth_headers,
        )
        assert response.status_code == 200, response.text


@pytest.mark.integration
@pytest.mark.confirmation
class TestDOCSCHEDBE004DoctorIdentityIntegrity:
    """DOCSCHED-BE-004: doctor_id — это doctors.id, а не users.id."""

    def test_admin_without_doctor_profile_creates_unowned_visit(
        self, client, db_session, auth_headers, test_patient, test_service
    ):
        """Admin без профиля врача: визит без врача (D-08 fail-closed на
        этапе выдачи номера), а не FK-ошибка и не подставной doctor_id."""
        visit_date = _clinic_today(db_session) + timedelta(days=1)

        response = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=_schedule_payload(test_patient, test_service, visit_date=visit_date),
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

        visit = db_session.get(Visit, response.json()["visit_id"])
        admin = (
            db_session.query(User)
            .filter(User.username == "test_admin")
            .first()
        )
        assert admin is not None
        assert visit.doctor_id is None, (
            "visit.doctor_id заполнен user id администратора без профиля врача"
        )
        assert visit.doctor_id != admin.id

    def test_admin_user_id_collision_does_not_assign_unrelated_doctor(
        self, client, db_session, test_patient, test_service
    ):
        """Числовое совпадение User.id с чужим Doctor.id не должно
        тихо привязывать визит к этому врачу."""
        suffix = _unique_suffix()
        collision_admin = User(
            id=9_876_543,
            username=f"coll_admin_{suffix}",
            email=f"coll_admin_{suffix}@test.com",
            full_name="Collision Admin",
            hashed_password="not-a-real-hash",
            role="Admin",
            is_active=True,
            is_superuser=False,
        )
        unrelated_user = User(
            username=f"unrelated_doc_{suffix}",
            email=f"unrelated_doc_{suffix}@test.com",
            full_name="Unrelated Doc User",
            hashed_password="not-a-real-hash",
            role="Doctor",
            is_active=True,
            is_superuser=False,
        )
        db_session.add_all([collision_admin, unrelated_user])
        db_session.commit()

        unrelated_doctor = Doctor(
            id=collision_admin.id,
            user_id=unrelated_user.id,
            specialty="Кардиология",
            active=True,
        )
        db_session.add(unrelated_doctor)
        db_session.commit()

        headers = {"Authorization": f"Bearer {mint_access_token(collision_admin)}"}
        visit_date = _clinic_today(db_session) + timedelta(days=1)

        response = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=_schedule_payload(test_patient, test_service, visit_date=visit_date),
            headers=headers,
        )
        assert response.status_code == 200, response.text

        visit = db_session.get(Visit, response.json()["visit_id"])
        assert visit.doctor_id is None, (
            "визит тихо привязан к чужому врачу через числовое совпадение id"
        )


@pytest.mark.integration
@pytest.mark.confirmation
class TestDOCSCHEDBE005VisitTimeContract:
    """DOCSCHED-BE-005: visit_time — канонический HH:MM или отсутствие."""

    @pytest.mark.parametrize(
        "visit_time", ["29:99", "notime", "9:00", "10:0", "10:60", "0100"]
    )
    def test_invalid_visit_time_rejected(
        self,
        client,
        db_session,
        cardio_auth_headers,
        test_doctor,
        test_service,
        visit_time,
    ):
        patient = _make_patient(db_session)
        _prior_context_visit(db_session, patient=patient, doctor=test_doctor)
        visit_date = _clinic_today(db_session) + timedelta(days=1)

        response = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=_schedule_payload(
                patient, test_service, visit_date=visit_date, visit_time=visit_time
            ),
            headers=cardio_auth_headers,
        )
        assert response.status_code == 422, (
            f"некорректное visit_time={visit_time!r} принято в pending-визит"
        )
        assert _pending_visits(db_session, patient_id=patient.id) == []

    @pytest.mark.parametrize("visit_time", ["00:00", "23:59", None])
    def test_boundary_valid_times_accepted(
        self,
        client,
        db_session,
        cardio_auth_headers,
        test_doctor,
        test_service,
        visit_time,
    ):
        patient = _make_patient(db_session)
        _prior_context_visit(db_session, patient=patient, doctor=test_doctor)
        visit_date = _clinic_today(db_session) + timedelta(days=1)

        payload = _schedule_payload(patient, test_service, visit_date=visit_date)
        if visit_time is None:
            payload.pop("visit_time")
        else:
            payload["visit_time"] = visit_time

        response = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=payload,
            headers=cardio_auth_headers,
        )
        assert response.status_code == 200, response.text
        visit = db_session.get(Visit, response.json()["visit_id"])
        assert visit.visit_time == visit_time


@pytest.mark.integration
@pytest.mark.confirmation
class TestDOCSCHEDServiceInputValidation:
    """DOCVISIT-BE-002 root risk через второй вход: quantity/custom_price
    валидируются до персистентности; custom_price=0 — осознанный ноль."""

    @pytest.mark.parametrize(
        "service_payload",
        [
            {"quantity": 0},
            {"quantity": -2},
            {"custom_price": -1.0},
            {"custom_price": float("nan")},
            {"custom_price": float("inf")},
        ],
    )
    def test_invalid_service_inputs_rejected_before_persistence(
        self,
        client,
        db_session,
        cardio_auth_headers,
        test_doctor,
        test_service,
        service_payload,
    ):
        patient = _make_patient(db_session)
        _prior_context_visit(db_session, patient=patient, doctor=test_doctor)
        visit_date = _clinic_today(db_session) + timedelta(days=1)

        line = {"service_id": test_service.id, "quantity": 1}
        line.update(service_payload)

        payload = _schedule_payload(
            patient, test_service, visit_date=visit_date, services=[line]
        )
        # Не-конечные float не являются JSON-стандартом: httpx json= их
        # отклоняет. Отправляем RAW-тело с allow_nan=True — так «кривой»
        # клиент реально может доставить NaN/Infinity на сервер.
        if isinstance(service_payload.get("custom_price"), float) and not math.isfinite(
            service_payload["custom_price"]
        ):
            response = client.post(
                "/api/v1/doctor/visits/schedule-next",
                content=json.dumps(payload, allow_nan=True),
                headers={
                    **cardio_auth_headers,
                    "Content-Type": "application/json",
                },
            )
        else:
            response = client.post(
                "/api/v1/doctor/visits/schedule-next",
                json=payload,
                headers=cardio_auth_headers,
            )
        assert response.status_code == 422, (
            f"некорректная строка услуги {service_payload} принята"
        )
        assert _pending_visits(db_session, patient_id=patient.id) == []

    def test_explicit_zero_is_recorded_for_review_at_the_regular_price(
        self, client, db_session, cardio_auth_headers, test_doctor
    ):
        """A proposed zero is exact and remains pending review."""
        override_service = _make_service(db_session, price=150000.0)
        override_service.allow_doctor_price_override = True
        db_session.commit()
        paid_service = _make_service(db_session, price=80000.0)
        patient = _make_patient(db_session)
        _prior_context_visit(db_session, patient=patient, doctor=test_doctor)
        visit_date = _clinic_today(db_session) + timedelta(days=1)

        response = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=_schedule_payload(
                patient,
                paid_service,
                visit_date=visit_date,
                services=[
                    {"service_id": override_service.id, "quantity": 1, "custom_price": 0},
                    {"service_id": paid_service.id, "quantity": 1},
                ],
            ),
            headers=cardio_auth_headers,
        )
        assert response.status_code == 200, response.text

        visit_id = response.json()["visit_id"]
        line = (
            db_session.query(VisitService)
            .filter(VisitService.visit_id == visit_id, VisitService.service_id == override_service.id)
            .one()
        )
        assert line.price == Decimal("150000.00")
        override = db_session.query(DoctorPriceOverride).filter_by(
            visit_id=visit_id, target_visit_service_id=line.id,
        ).one()
        assert (override.new_price, override.status) == (Decimal("0.00"), "pending")
        assert response.json()["price_override_requests"] == [
            {"id": override.id, "visit_service_id": line.id, "status": "pending"},
        ]
        assert math.isclose(
            response.json()["confirmation"]["total_amount"], 230000.0
        )


@pytest.mark.integration
@pytest.mark.confirmation
def test_schedule_next_issues_usable_token_after_initial_service_rows(
    client, db_session, cardio_auth_headers, test_doctor, test_service, monkeypatch,
):
    """The real HTTP creation path issues its token after service fencing."""
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    from app.api.v1.endpoints.doctor_integration import _visits

    path = Path(__file__).resolve().parents[2] / "alembic/versions/0102_visit_confirmation_context.py"
    spec = importlib.util.spec_from_file_location("context_schedule_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    conn = db_session.connection()
    # The test metadata includes the new column already; apply the actual
    # migration against the equivalent pre-migration schema.
    conn.exec_driver_sql("ALTER TABLE visits DROP COLUMN confirmation_context_epoch")
    migration.op = Operations(MigrationContext.configure(conn))
    migration.upgrade()
    seen_tokens = []

    stage = _visits.stage_visit_invitation

    def record_invitation(db, **kwargs):
        visit = db.query(Visit).filter(Visit.id == kwargs["visit_id"]).populate_existing().one()
        assert db.query(VisitService).filter_by(visit_id=visit.id).count() == 1
        seen_tokens.append(visit.confirmation_token)
        return stage(db, **kwargs)

    monkeypatch.setattr(_visits, "stage_visit_invitation", record_invitation)
    try:
        patient = _make_patient(db_session)
        _prior_context_visit(db_session, patient=patient, doctor=test_doctor)
        payload = _schedule_payload(patient, test_service, visit_date=_clinic_today(db_session) + timedelta(days=1))
        response = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=cardio_auth_headers)
        assert response.status_code == 200, response.text
        body = response.json()
        db_session.expire_all()
        visit = db_session.get(Visit, body["visit_id"])
        assert visit is not None and visit.confirmation_token
        assert body["confirmation"]["token"] == visit.confirmation_token
        assert seen_tokens == [visit.confirmation_token]
        assert db_session.query(VisitService).filter_by(visit_id=visit.id).count() == 1
    finally:
        # Restore metadata-created test DB for other test modules.
        migration.op = Operations(MigrationContext.configure(db_session.connection()))
        migration.downgrade()
        db_session.connection().exec_driver_sql(
            "ALTER TABLE visits ADD COLUMN confirmation_context_epoch BIGINT NOT NULL DEFAULT 0"
        )
