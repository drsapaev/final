from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.derma_examination import DermaExamination
from app.models.derma_procedure import DermaProcedure
from app.models.emr_v2 import EMRRecord
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit


def _suffix() -> str:
    return uuid4().hex[:10]


def _create_doctor_user(db_session, *, label: str) -> tuple[User, Doctor]:
    suffix = _suffix()
    user = User(
        username=f"derma_guard_{label}_{suffix}",
        email=f"derma-guard-{label}-{suffix}@test.local",
        full_name=f"Derma Guard {label}",
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doctor = Doctor(
        user_id=user.id,
        specialty="dermatology",
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return user, doctor


def _create_patient(db_session, *, label: str) -> Patient:
    suffix = _suffix()
    patient = Patient(
        first_name=f"Derma {label}",
        last_name="OwnerGuard",
        phone=f"+99891{suffix[:7]}",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _create_visit(db_session, *, patient: Patient, doctor: Doctor) -> Visit:
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=date.today(),
        status="open",
        source="desk",
        department="dermatology",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)
    return visit


def _doctor_headers(client, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "doctor123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


EXAMINATION_PAYLOAD = {
    "examination_date": date.today().isoformat(),
    "skin_type": "combination",
    "skin_condition": "Чувствительная кожа",
    "lesions": "Локальная эритема",
    "diagnosis": "Розацеа под вопросом",
    "treatment_plan": "Мягкий уход и повторный контроль",
}

PROCEDURE_PAYLOAD = {
    "procedure_date": date.today().isoformat(),
    "procedure_type": "laser",
    "area_treated": "Щеки",
    "products_used": "Cooling gel",
    "results": "Покраснение минимальное",
    "follow_up": "Контроль через 14 дней",
    "total_cost": 125000,
}


@pytest.mark.integration
class TestDermaApi:
    def test_legacy_examination_writes_are_gone_but_reads_still_list(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_visit,
        admin_user,
    ):
        """P2-4a: POST /derma/examinations закрыт (410) для всех ролей —
        таблица read-only, новые осмотры живут в specialty_data ЭМК.
        GET-чтение истории не изменилось: заранее засеянные строки
        возвращаются владельцу-админу без изменений."""
        seeded = DermaExamination(
            patient_id=test_patient.id,
            visit_id=test_visit.id,
            doctor_id=admin_user.id,
            examination_date=date.today(),
            skin_type="combination",
            skin_condition="Чувствительная кожа",
            lesions="Локальная эритема",
            diagnosis="Розацеа под вопросом",
            treatment_plan="Мягкий уход и повторный контроль",
        )
        db_session.add(seeded)
        db_session.commit()
        db_session.refresh(seeded)

        write_response = client.post(
            "/api/v1/derma/examinations",
            json={
                **EXAMINATION_PAYLOAD,
                "patient_id": test_patient.id,
                "visit_id": test_visit.id,
            },
            headers=auth_headers,
        )
        assert write_response.status_code == 410
        assert "ЭМК" in write_response.json()["detail"]
        assert (
            db_session.query(DermaExamination)
            .filter(DermaExamination.patient_id == test_patient.id)
            .count()
            == 1
        )

        list_response = client.get(
            f"/api/v1/derma/examinations?patient_id={test_patient.id}&limit=10",
            headers=auth_headers,
        )
        assert list_response.status_code == 200
        listed = list_response.json()
        assert [item["id"] for item in listed] == [seeded.id]
        assert listed[0]["patient_id"] == test_patient.id
        assert listed[0]["diagnosis"] == seeded.diagnosis

    def test_legacy_procedure_writes_are_gone_but_reads_still_list(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_visit,
        admin_user,
    ):
        """P2-4a: POST /derma/procedures закрыт (410) для всех ролей —
        таблица read-only, новые процедуры живут в specialty_data ЭМК.
        GET-чтение истории не изменилось."""
        seeded = DermaProcedure(
            patient_id=test_patient.id,
            visit_id=test_visit.id,
            doctor_id=admin_user.id,
            procedure_date=date.today(),
            procedure_type="laser",
            area_treated="Щеки",
            products_used="Cooling gel",
            results="Покраснение минимальное",
            follow_up="Контроль через 14 дней",
            total_cost=125000,
        )
        db_session.add(seeded)
        db_session.commit()
        db_session.refresh(seeded)

        write_response = client.post(
            "/api/v1/derma/procedures",
            json={
                **PROCEDURE_PAYLOAD,
                "patient_id": test_patient.id,
                "visit_id": test_visit.id,
            },
            headers=auth_headers,
        )
        assert write_response.status_code == 410
        assert "ЭМК" in write_response.json()["detail"]
        assert (
            db_session.query(DermaProcedure)
            .filter(DermaProcedure.patient_id == test_patient.id)
            .count()
            == 1
        )

        list_response = client.get(
            f"/api/v1/derma/procedures?patient_id={test_patient.id}&limit=10",
            headers=auth_headers,
        )
        assert list_response.status_code == 200
        listed = list_response.json()
        assert [item["id"] for item in listed] == [seeded.id]
        assert listed[0]["patient_id"] == test_patient.id
        assert listed[0]["procedure_type"] == seeded.procedure_type

    def test_legacy_write_endpoints_are_gone_for_doctor_role(
        self,
        client,
        db_session,
    ):
        """P2-4a: fail-closed для врача (Doctor) на своих и чужих пациентах —
        410 возвращается ДО каких-либо ownership-проверок, эндпоинт исчез
        как источник записи; новые данные создаются только в ЭМК."""
        own_user, own_doctor = _create_doctor_user(db_session, label="own")
        _other_user, other_doctor = _create_doctor_user(db_session, label="other")
        own_patient = _create_patient(db_session, label="own")
        other_patient = _create_patient(db_session, label="other")
        own_visit = _create_visit(db_session, patient=own_patient, doctor=own_doctor)
        other_visit = _create_visit(
            db_session, patient=other_patient, doctor=other_doctor
        )
        headers = _doctor_headers(client, own_user)

        own_exam_write = client.post(
            "/api/v1/derma/examinations",
            json={
                **EXAMINATION_PAYLOAD,
                "patient_id": own_patient.id,
                "visit_id": own_visit.id,
            },
            headers=headers,
        )
        assert own_exam_write.status_code == 410

        foreign_exam_write = client.post(
            "/api/v1/derma/examinations",
            json={
                **EXAMINATION_PAYLOAD,
                "patient_id": other_patient.id,
                "visit_id": other_visit.id,
            },
            headers=headers,
        )
        assert foreign_exam_write.status_code == 410

        own_procedure_write = client.post(
            "/api/v1/derma/procedures",
            json={
                **PROCEDURE_PAYLOAD,
                "patient_id": own_patient.id,
                "visit_id": own_visit.id,
            },
            headers=headers,
        )
        assert own_procedure_write.status_code == 410

        foreign_procedure_write = client.post(
            "/api/v1/derma/procedures",
            json={
                **PROCEDURE_PAYLOAD,
                "patient_id": other_patient.id,
                "visit_id": other_visit.id,
            },
            headers=headers,
        )
        assert foreign_procedure_write.status_code == 410

        assert db_session.query(DermaExamination).count() == 0
        assert db_session.query(DermaProcedure).count() == 0

    def test_doctor_derma_records_are_limited_to_owned_patients(
        self,
        client,
        db_session,
    ):
        own_user, own_doctor = _create_doctor_user(db_session, label="own")
        _other_user, other_doctor = _create_doctor_user(db_session, label="other")
        own_patient = _create_patient(db_session, label="own")
        other_patient = _create_patient(db_session, label="other")
        own_visit = _create_visit(db_session, patient=own_patient, doctor=own_doctor)
        other_visit = _create_visit(db_session, patient=other_patient, doctor=other_doctor)
        own_exam = DermaExamination(
            patient_id=own_patient.id,
            visit_id=own_visit.id,
            doctor_id=own_user.id,
            examination_date=date.today(),
            skin_type="combination",
            diagnosis="owned diagnosis",
        )
        other_exam = DermaExamination(
            patient_id=other_patient.id,
            visit_id=other_visit.id,
            doctor_id=None,
            examination_date=date.today(),
            skin_type="dry",
            diagnosis="foreign diagnosis",
        )
        own_procedure = DermaProcedure(
            patient_id=own_patient.id,
            visit_id=own_visit.id,
            doctor_id=own_user.id,
            procedure_date=date.today(),
            procedure_type="laser",
            total_cost=100000,
        )
        other_procedure = DermaProcedure(
            patient_id=other_patient.id,
            visit_id=other_visit.id,
            doctor_id=None,
            procedure_date=date.today(),
            procedure_type="peel",
            total_cost=200000,
        )
        db_session.add_all([own_exam, other_exam, own_procedure, other_procedure])
        db_session.commit()
        db_session.refresh(own_exam)
        db_session.refresh(other_exam)
        db_session.refresh(own_procedure)
        db_session.refresh(other_procedure)
        headers = _doctor_headers(client, own_user)

        exams_response = client.get("/api/v1/derma/examinations?limit=20", headers=headers)
        assert exams_response.status_code == 200
        exam_ids = {item["id"] for item in exams_response.json()}
        assert own_exam.id in exam_ids
        assert other_exam.id not in exam_ids

        procedures_response = client.get("/api/v1/derma/procedures?limit=20", headers=headers)
        assert procedures_response.status_code == 200
        procedure_ids = {item["id"] for item in procedures_response.json()}
        assert own_procedure.id in procedure_ids
        assert other_procedure.id not in procedure_ids

        foreign_exam_read_response = client.get(
            f"/api/v1/derma/examinations?patient_id={other_patient.id}",
            headers=headers,
        )
        assert foreign_exam_read_response.status_code == 403

        foreign_procedure_read_response = client.get(
            f"/api/v1/derma/procedures?patient_id={other_patient.id}",
            headers=headers,
        )
        assert foreign_procedure_read_response.status_code == 403

    def test_legacy_examination_write_rejects_missing_patient_with_gone(
        self,
        client,
        auth_headers,
        test_visit,
    ):
        """P2-4a: 410 возвращается ДО валидации пациента — эндпоинт записи
        исчез целиком, любых полезных нагрузок, включая некорректные."""
        payload = {
            "patient_id": 999999,
            "visit_id": test_visit.id,
            "examination_date": date.today().isoformat(),
            "skin_type": "dry",
        }

        response = client.post(
            "/api/v1/derma/examinations",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 410


# --- P2-4b: unified history surface (EMR specialty_data + legacy fallback) ---

def _create_emr(
    db_session,
    *,
    patient: Patient,
    visit: Visit,
    user: User,
    data: dict,
    created_at: datetime | None = None,
) -> EMRRecord:
    extra = {"created_at": created_at} if created_at is not None else {}
    emr = EMRRecord(
        patient_id=patient.id,
        visit_id=visit.id,
        version=1,
        data=data,
        status="draft",
        created_by=user.id,
        **extra,
    )
    db_session.add(emr)
    db_session.commit()
    db_session.refresh(emr)
    return emr


def _create_emr_fillers(
    db_session,
    *,
    patient: Patient,
    doctor: Doctor,
    user: User,
    count: int,
    base_created_at: datetime,
) -> None:
    """Non-derma active EMRs, one per visit, each newer than the previous.

    Used by the triage-P1 regression: with a recency cap in place these
    newer records would push older derma EMRs out of the scan window.
    """
    visits = [
        Visit(
            patient_id=patient.id,
            doctor_id=doctor.id,
            visit_date=date.today(),
            status="open",
            source="desk",
            department="dermatology",
        )
        for _ in range(count)
    ]
    db_session.add_all(visits)
    db_session.commit()
    db_session.add_all(
        EMRRecord(
            patient_id=patient.id,
            visit_id=visit.id,
            version=1,
            data={"specialty": "cardiology"},
            status="draft",
            created_by=user.id,
            created_at=base_created_at + timedelta(minutes=index),
        )
        for index, visit in enumerate(visits)
    )
    db_session.commit()


def _derma_emr_data() -> dict:
    return {
        "specialty": "dermatology",
        "diagnosis": {"main": "Розацеа", "icd10_code": "L71.1", "secondary": []},
        "specialty_data": {
            "skin_type": "combination",
            "skin_condition": "Чувствительная кожа",
            "lesions": "Локальная эритема",
            "distribution": "Щеки",
            "symptoms": "Жжение",
            "treatment_plan": "Мягкий уход",
            "localization": {"description": "Щеки и нос"},
            "procedures": [
                {
                    "procedure_date": date.today().isoformat(),
                    "procedure_type": "Мезотерапия",
                    "area_treated": "Лицо",
                    "products_used": "HA gel",
                    "results": "Гиперемия слабая",
                    "follow_up": "Контроль 14 дней",
                    "recorded_at": f"{date.today().isoformat()}T10:00:00Z",
                },
                {
                    "procedure_date": date.today().isoformat(),
                    "procedure_type": "Чистка",
                    "area_treated": "Лоб",
                    "recorded_at": f"{date.today().isoformat()}T09:00:00Z",
                },
            ],
        },
    }


@pytest.mark.integration
class TestDermaEmrHistory:
    def test_emr_derma_history_is_served_alongside_legacy(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_visit,
        test_doctor,
        admin_user,
    ):
        """P2-4b: GET-история объединяет два read-only источника —
        осмотры/процедуры из specialty_data ЭМК (source=emr) и read-only
        legacy-строки закрытых таблиц (source=legacy), newest-first."""
        emr_visit = _create_visit(db_session, patient=test_patient, doctor=test_doctor)
        emr = _create_emr(
            db_session,
            patient=test_patient,
            visit=emr_visit,
            user=admin_user,
            data=_derma_emr_data(),
        )

        legacy_exam = DermaExamination(
            patient_id=test_patient.id,
            visit_id=test_visit.id,
            doctor_id=admin_user.id,
            examination_date=date.today() - timedelta(days=1),
            skin_type="dry",
            diagnosis="legacy diagnosis",
        )
        legacy_procedure = DermaProcedure(
            patient_id=test_patient.id,
            visit_id=test_visit.id,
            doctor_id=admin_user.id,
            procedure_date=date.today() - timedelta(days=1),
            procedure_type="legacy peel",
            total_cost=99000,
        )
        db_session.add_all([legacy_exam, legacy_procedure])
        db_session.commit()
        db_session.refresh(legacy_exam)
        db_session.refresh(legacy_procedure)

        exams_response = client.get(
            f"/api/v1/derma/examinations?patient_id={test_patient.id}&limit=10",
            headers=auth_headers,
        )
        assert exams_response.status_code == 200
        exams = exams_response.json()
        assert [item["id"] for item in exams] == [f"emr-{emr.id}", legacy_exam.id]
        assert [item["source"] for item in exams] == ["emr", "legacy"]
        emr_exam = exams[0]
        assert emr_exam["patient_id"] == test_patient.id
        assert emr_exam["visit_id"] == emr_visit.id
        assert emr_exam["examination_date"] == date.today().isoformat()
        assert emr_exam["skin_type"] == "combination"
        assert emr_exam["skin_condition"] == "Чувствительная кожа"
        assert emr_exam["diagnosis"] == "Розацеа"
        assert emr_exam["treatment_plan"] == "Мягкий уход"
        assert exams[1]["diagnosis"] == "legacy diagnosis"

        procedures_response = client.get(
            f"/api/v1/derma/procedures?patient_id={test_patient.id}&limit=10",
            headers=auth_headers,
        )
        assert procedures_response.status_code == 200
        procedures = procedures_response.json()
        assert [item["id"] for item in procedures] == [
            f"emr-{emr.id}-0",
            f"emr-{emr.id}-1",
            legacy_procedure.id,
        ]
        assert [item["source"] for item in procedures] == ["emr", "emr", "legacy"]
        assert procedures[0]["procedure_type"] == "Мезотерапия"
        assert procedures[0]["area_treated"] == "Лицо"
        assert procedures[1]["procedure_type"] == "Чистка"
        assert procedures[0]["total_cost"] is None
        assert procedures[2]["total_cost"] == 99000
        assert procedures[2]["procedure_type"] == "legacy peel"

    def test_emr_derma_history_is_scoped_to_doctor_patients(
        self,
        client,
        db_session,
    ):
        """P2-4b: ЭМК-строки истории скоупятся тем же контрактом, что и
        legacy-чтение — врач видит только своих пациентов; чужой patient_id
        по-прежнему 403."""
        own_user, own_doctor = _create_doctor_user(db_session, label="p24bown")
        _other_user, other_doctor = _create_doctor_user(db_session, label="p24bother")
        own_patient = _create_patient(db_session, label="p24bown")
        other_patient = _create_patient(db_session, label="p24bother")
        own_visit = _create_visit(db_session, patient=own_patient, doctor=own_doctor)
        other_visit = _create_visit(db_session, patient=other_patient, doctor=other_doctor)
        emr_own = _create_emr(
            db_session,
            patient=own_patient,
            visit=own_visit,
            user=own_user,
            data=_derma_emr_data(),
        )
        emr_other = _create_emr(
            db_session,
            patient=other_patient,
            visit=other_visit,
            user=_other_user,
            data=_derma_emr_data(),
        )
        headers = _doctor_headers(client, own_user)

        foreign_exam_read = client.get(
            f"/api/v1/derma/examinations?patient_id={other_patient.id}",
            headers=headers,
        )
        assert foreign_exam_read.status_code == 403

        foreign_procedure_read = client.get(
            f"/api/v1/derma/procedures?patient_id={other_patient.id}",
            headers=headers,
        )
        assert foreign_procedure_read.status_code == 403

        exams_response = client.get("/api/v1/derma/examinations?limit=20", headers=headers)
        assert exams_response.status_code == 200
        exams = exams_response.json()
        exam_ids = {item["id"] for item in exams}
        assert f"emr-{emr_own.id}" in exam_ids
        assert f"emr-{emr_other.id}" not in exam_ids
        assert {item["patient_id"] for item in exams} == {own_patient.id}

        procedures_response = client.get("/api/v1/derma/procedures?limit=20", headers=headers)
        assert procedures_response.status_code == 200
        procedures = procedures_response.json()
        procedure_ids = {item["id"] for item in procedures}
        assert f"emr-{emr_own.id}-0" in procedure_ids
        assert f"emr-{emr_other.id}-0" not in procedure_ids
        assert {item["patient_id"] for item in procedures} == {own_patient.id}

    def test_empty_dermatology_emr_yields_no_history_row(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
        admin_user,
    ):
        """P2-4b: пустой черновик ЭМК дерматологии (скелет без данных) и
        мусорные записи процедур не создают строк истории."""
        empty_visit = _create_visit(db_session, patient=test_patient, doctor=test_doctor)
        _create_emr(
            db_session,
            patient=test_patient,
            visit=empty_visit,
            user=admin_user,
            data={
                "specialty": "dermatology",
                "specialty_data": {
                    "skin_type": "",
                    "procedures": [{"procedure_type": "   "}],
                },
            },
        )

        exams_response = client.get(
            f"/api/v1/derma/examinations?patient_id={test_patient.id}&limit=10",
            headers=auth_headers,
        )
        assert exams_response.status_code == 200
        assert all(
            not str(item["id"]).startswith("emr-") for item in exams_response.json()
        )

        procedures_response = client.get(
            f"/api/v1/derma/procedures?patient_id={test_patient.id}&limit=10",
            headers=auth_headers,
        )
        assert procedures_response.status_code == 200
        assert procedures_response.json() == []

    def test_emr_history_scan_is_exhaustive_beyond_500_emrs(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_visit,
        test_doctor,
        admin_user,
    ):
        """Triage P1 (#3491 review): recency-cap удалён — история
        эквивалентна полному union. Старая дерматологическая ЭМК обязана
        оставаться в истории, даже когда в скоупе пациента 505 более
        новых активных ЭМК (ранее cap 500 стоял ДО фильтра
        specialty="dermatology" и до формирования строк процедур)."""
        target_visit = _create_visit(db_session, patient=test_patient, doctor=test_doctor)
        target = _create_emr(
            db_session,
            patient=test_patient,
            visit=target_visit,
            user=admin_user,
            data=_derma_emr_data(),
            created_at=datetime(2025, 1, 5, 9, 0, 0),
        )
        _create_emr_fillers(
            db_session,
            patient=test_patient,
            doctor=test_doctor,
            user=admin_user,
            count=505,
            base_created_at=datetime(2026, 1, 1, 10, 0, 0),
        )

        exams_response = client.get(
            f"/api/v1/derma/examinations?patient_id={test_patient.id}&limit=10",
            headers=auth_headers,
        )
        assert exams_response.status_code == 200
        assert f"emr-{target.id}" in [item["id"] for item in exams_response.json()]

        procedures_response = client.get(
            f"/api/v1/derma/procedures?patient_id={test_patient.id}&limit=10",
            headers=auth_headers,
        )
        assert procedures_response.status_code == 200
        procedure_ids = [item["id"] for item in procedures_response.json()]
        assert f"emr-{target.id}-0" in procedure_ids
        assert f"emr-{target.id}-1" in procedure_ids

        history_response = client.get(
            f"/api/v1/derma/history?patient_id={test_patient.id}&limit=10",
            headers=auth_headers,
        )
        assert history_response.status_code == 200
        history_payload = history_response.json()
        assert f"emr-{target.id}" in [
            item["id"] for item in history_payload["examinations"]
        ]
        assert f"emr-{target.id}-0" in [
            item["id"] for item in history_payload["procedures"]
        ]

    def test_doctor_wide_history_scan_is_exhaustive_across_patients(
        self,
        client,
        db_session,
    ):
        """Triage P1 (#3491 review): без patient_id капа не существует и на
        весь набор разрешённых пациентов врача — ЭМК другого пациента
        врача остаётся в истории за 505 более новых ЭМК первого пациента
        (ранее cap применялся к скану всей выборки врача)."""
        own_user, own_doctor = _create_doctor_user(db_session, label="p1scan")
        patient_a = _create_patient(db_session, label="p1scana")
        patient_b = _create_patient(db_session, label="p1scanb")

        target_visit = _create_visit(db_session, patient=patient_b, doctor=own_doctor)
        target_b = _create_emr(
            db_session,
            patient=patient_b,
            visit=target_visit,
            user=own_user,
            data=_derma_emr_data(),
            created_at=datetime(2025, 1, 5, 9, 0, 0),
        )
        _create_emr_fillers(
            db_session,
            patient=patient_a,
            doctor=own_doctor,
            user=own_user,
            count=505,
            base_created_at=datetime(2026, 1, 1, 10, 0, 0),
        )
        headers = _doctor_headers(client, own_user)

        exams_response = client.get("/api/v1/derma/examinations?limit=20", headers=headers)
        assert exams_response.status_code == 200
        exams = exams_response.json()
        assert f"emr-{target_b.id}" in [item["id"] for item in exams]
        assert {item["patient_id"] for item in exams} == {patient_b.id}

        procedures_response = client.get("/api/v1/derma/procedures?limit=20", headers=headers)
        assert procedures_response.status_code == 200
        procedure_ids = [item["id"] for item in procedures_response.json()]
        assert f"emr-{target_b.id}-0" in procedure_ids
        assert f"emr-{target_b.id}-1" in procedure_ids

        history_response = client.get("/api/v1/derma/history?limit=20", headers=headers)
        assert history_response.status_code == 200
        history_payload = history_response.json()
        assert f"emr-{target_b.id}" in [
            item["id"] for item in history_payload["examinations"]
        ]
        assert f"emr-{target_b.id}-0" in [
            item["id"] for item in history_payload["procedures"]
        ]

    def test_derma_history_combined_endpoint_single_scan(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_visit,
        test_doctor,
        admin_user,
    ):
        """Triage P2 (#3491 review): GET /derma/history — один скан
        emr_records и одна загрузка visits обслуживают обе секции; секции
        идентичны гранулярным GET; скоупинг тот же (чужой patient_id —
        403)."""
        emr_visit = _create_visit(db_session, patient=test_patient, doctor=test_doctor)
        emr = _create_emr(
            db_session,
            patient=test_patient,
            visit=emr_visit,
            user=admin_user,
            data=_derma_emr_data(),
        )
        legacy_exam = DermaExamination(
            patient_id=test_patient.id,
            visit_id=test_visit.id,
            doctor_id=admin_user.id,
            examination_date=date.today() - timedelta(days=1),
            skin_type="dry",
            diagnosis="legacy diagnosis",
        )
        legacy_procedure = DermaProcedure(
            patient_id=test_patient.id,
            visit_id=test_visit.id,
            doctor_id=admin_user.id,
            procedure_date=date.today() - timedelta(days=1),
            procedure_type="legacy peel",
            total_cost=99000,
        )
        db_session.add_all([legacy_exam, legacy_procedure])
        db_session.commit()

        statements: list[str] = []

        def _record_statement(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement.lower())

        engine = db_session.get_bind()
        event.listen(engine, "before_cursor_execute", _record_statement)
        try:
            history_response = client.get(
                f"/api/v1/derma/history?patient_id={test_patient.id}&limit=10",
                headers=auth_headers,
            )
        finally:
            event.remove(engine, "before_cursor_execute", _record_statement)
        assert history_response.status_code == 200
        payload = history_response.json()

        emr_scans = [s for s in statements if "from emr_records" in s]
        assert len(emr_scans) == 1, (
            f"combined history must scan emr_records exactly once, got {len(emr_scans)}"
        )
        visit_loads = [s for s in statements if "from visits" in s]
        assert len(visit_loads) == 1, (
            f"combined history must load visits exactly once, got {len(visit_loads)}"
        )

        assert [item["id"] for item in payload["examinations"]] == [
            f"emr-{emr.id}",
            legacy_exam.id,
        ]
        assert [item["id"] for item in payload["procedures"]] == [
            f"emr-{emr.id}-0",
            f"emr-{emr.id}-1",
            legacy_procedure.id,
        ]

        exams_response = client.get(
            f"/api/v1/derma/examinations?patient_id={test_patient.id}&limit=10",
            headers=auth_headers,
        )
        procs_response = client.get(
            f"/api/v1/derma/procedures?patient_id={test_patient.id}&limit=10",
            headers=auth_headers,
        )
        assert exams_response.status_code == 200
        assert procs_response.status_code == 200
        assert payload["examinations"] == exams_response.json()
        assert payload["procedures"] == procs_response.json()

        other_user, _other_doctor = _create_doctor_user(db_session, label="p24bcomb")
        foreign_headers = _doctor_headers(client, other_user)
        foreign_response = client.get(
            f"/api/v1/derma/history?patient_id={test_patient.id}&limit=10",
            headers=foreign_headers,
        )
        assert foreign_response.status_code == 403

    def test_derma_history_combined_doctor_scope_resolved_once(
        self,
        client,
        db_session,
    ):
        """Triage P2 (#3491 review): комбинированная история для врача —
        тот же профиль: один скан emr_records, одна загрузка Visit-данных
        и ОДНОКРАТНЫЙ резолв RBAC-скоупа разрешённых пациентов (без фикса
        скоуп-запрос visits.doctor_id выполнялся бы повторно для legacy
        секций)."""
        own_user, own_doctor = _create_doctor_user(db_session, label="p24bcombdoc")
        own_patient = _create_patient(db_session, label="p24bcombdoc")
        own_visit = _create_visit(db_session, patient=own_patient, doctor=own_doctor)
        emr = _create_emr(
            db_session,
            patient=own_patient,
            visit=own_visit,
            user=own_user,
            data=_derma_emr_data(),
        )
        headers = _doctor_headers(client, own_user)

        statements: list[str] = []

        def _record_statement(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement.lower())

        engine = db_session.get_bind()
        event.listen(engine, "before_cursor_execute", _record_statement)
        try:
            history_response = client.get(
                "/api/v1/derma/history?limit=20", headers=headers
            )
        finally:
            event.remove(engine, "before_cursor_execute", _record_statement)
        assert history_response.status_code == 200
        payload = history_response.json()
        assert f"emr-{emr.id}" in [item["id"] for item in payload["examinations"]]
        assert f"emr-{emr.id}-0" in [item["id"] for item in payload["procedures"]]

        assert len([s for s in statements if "from emr_records" in s]) == 1, (
            "combined history must scan emr_records exactly once"
        )
        assert len([s for s in statements if "visits.doctor_id in" in s]) == 1, (
            "RBAC allowed-patients scope must be resolved exactly once"
        )
        assert len([s for s in statements if "visits.id in" in s]) == 1, (
            "combined history must load Visit data exactly once"
        )

    def test_emr_history_reads_both_procedure_keys(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
        admin_user,
    ):
        """Реконсиляция #3490/#3491: два писателя добавляют косметические
        процедуры в визитную ЭМК — быстрая форма панели пишет
        specialty_data.procedures, редактор EMR-секции —
        specialty_data.cosmetic_procedures. История обязана показывать
        записи обоих ключей (без потери данных)."""
        visit_quick = _create_visit(db_session, patient=test_patient, doctor=test_doctor)
        emr_quick = _create_emr(
            db_session,
            patient=test_patient,
            visit=visit_quick,
            user=admin_user,
            data={
                "specialty": "dermatology",
                "specialty_data": {
                    "skin_type": "combination",
                    "procedures": [
                        {
                            "procedure_type": "Мезотерапия",
                            "procedure_date": date.today().isoformat(),
                        },
                    ],
                },
            },
        )
        visit_section = _create_visit(db_session, patient=test_patient, doctor=test_doctor)
        emr_section = _create_emr(
            db_session,
            patient=test_patient,
            visit=visit_section,
            user=admin_user,
            data={
                "specialty": "dermatology",
                "specialty_data": {
                    "skin_type": "dry",
                    "cosmetic_procedures": [
                        {
                            "procedure_type": "Чистка",
                            "procedure_date": date.today().isoformat(),
                        },
                    ],
                },
            },
        )

        procedures_response = client.get(
            f"/api/v1/derma/procedures?patient_id={test_patient.id}&limit=10",
            headers=auth_headers,
        )
        assert procedures_response.status_code == 200
        procedure_ids = [item["id"] for item in procedures_response.json()]
        assert f"emr-{emr_quick.id}-0" in procedure_ids
        assert f"emr-{emr_section.id}-0" in procedure_ids
        procedure_types = {
            item["procedure_type"] for item in procedures_response.json()
        }
        assert {"Мезотерапия", "Чистка"} <= procedure_types

        history_response = client.get(
            f"/api/v1/derma/history?patient_id={test_patient.id}&limit=10",
            headers=auth_headers,
        )
        assert history_response.status_code == 200
        history_procedure_ids = [
            item["id"] for item in history_response.json()["procedures"]
        ]
        assert f"emr-{emr_quick.id}-0" in history_procedure_ids
        assert f"emr-{emr_section.id}-0" in history_procedure_ids
