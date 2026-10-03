from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

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


def _create_visit(
    db_session,
    *,
    patient: Patient,
    doctor: Doctor,
    visit_date: date | None = None,
) -> Visit:
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=visit_date or date.today(),
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


# --- P2-4b: unified history surface (EMR specialty_data + legacy fallback) ---

def _create_emr(
    db_session,
    *,
    patient: Patient,
    visit: Visit,
    user: User,
    data: dict,
) -> EMRRecord:
    emr = EMRRecord(
        patient_id=patient.id,
        visit_id=visit.id,
        version=1,
        data=data,
        status="draft",
        created_by=user.id,
    )
    db_session.add(emr)
    db_session.commit()
    db_session.refresh(emr)
    return emr


def _derma_emr_data() -> dict:
    """Dermatology EMR payload shaped exactly like the DermatologySection
    editor writes it (specialty_data.cosmetic_procedures is the canonical
    key of the merged #3490 editor, not `procedures`)."""
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
            "cosmetic_procedures": [
                {
                    "procedure_date": date.today().isoformat(),
                    "procedure_type": "Мезотерапия",
                    "area_treated": "Лицо",
                    "products_used": "HA gel",
                    "results": "Гиперемия слабая",
                    "follow_up": "Контроль 14 дней",
                },
                {
                    "procedure_date": date.today().isoformat(),
                    "procedure_type": "Чистка",
                    "area_treated": "Лоб",
                },
            ],
        },
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
        GET-чтение истории возвращает legacy-строки в конверте
        page/size/total/pages (P2-4b)."""
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
            f"/api/v1/derma/examinations?patient_id={test_patient.id}&size=10",
            headers=auth_headers,
        )
        assert list_response.status_code == 200
        payload = list_response.json()
        assert payload["total"] == 1
        assert payload["page"] == 1
        assert payload["size"] == 10
        assert payload["pages"] == 1
        assert [item["id"] for item in payload["items"]] == [seeded.id]
        assert payload["items"][0]["source"] == "legacy"
        assert payload["items"][0]["patient_id"] == test_patient.id
        assert payload["items"][0]["diagnosis"] == seeded.diagnosis

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
        GET-чтение истории возвращает legacy-строки в конверте."""
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
            f"/api/v1/derma/procedures?patient_id={test_patient.id}&size=10",
            headers=auth_headers,
        )
        assert list_response.status_code == 200
        payload = list_response.json()
        assert payload["total"] == 1
        assert [item["id"] for item in payload["items"]] == [seeded.id]
        assert payload["items"][0]["source"] == "legacy"
        assert payload["items"][0]["patient_id"] == test_patient.id
        assert payload["items"][0]["procedure_type"] == seeded.procedure_type

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

        exams_response = client.get(
            "/api/v1/derma/examinations?size=20", headers=headers
        )
        assert exams_response.status_code == 200
        exam_ids = {item["id"] for item in exams_response.json()["items"]}
        assert own_exam.id in exam_ids
        assert other_exam.id not in exam_ids

        procedures_response = client.get(
            "/api/v1/derma/procedures?size=20", headers=headers
        )
        assert procedures_response.status_code == 200
        procedure_ids = {item["id"] for item in procedures_response.json()["items"]}
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
        legacy-строки закрытых таблиц (source=legacy), newest-first,
        в конверте page/size/total/pages с точным total."""
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
            f"/api/v1/derma/examinations?patient_id={test_patient.id}&size=10",
            headers=auth_headers,
        )
        assert exams_response.status_code == 200
        exams_payload = exams_response.json()
        assert exams_payload["total"] == 2
        assert exams_payload["pages"] == 1
        assert exams_payload["page"] == 1
        assert [item["id"] for item in exams_payload["items"]] == [
            f"emr-{emr.id}",
            legacy_exam.id,
        ]
        assert [item["source"] for item in exams_payload["items"]] == [
            "emr",
            "legacy",
        ]
        emr_exam = exams_payload["items"][0]
        assert emr_exam["patient_id"] == test_patient.id
        assert emr_exam["visit_id"] == emr_visit.id
        assert emr_exam["examination_date"] == date.today().isoformat()
        assert emr_exam["skin_type"] == "combination"
        assert emr_exam["skin_condition"] == "Чувствительная кожа"
        assert emr_exam["diagnosis"] == "Розацеа"
        assert emr_exam["treatment_plan"] == "Мягкий уход"
        assert exams_payload["items"][1]["diagnosis"] == "legacy diagnosis"

        procedures_response = client.get(
            f"/api/v1/derma/procedures?patient_id={test_patient.id}&size=10",
            headers=auth_headers,
        )
        assert procedures_response.status_code == 200
        procedures_payload = procedures_response.json()
        assert procedures_payload["total"] == 3
        assert [item["id"] for item in procedures_payload["items"]] == [
            f"emr-{emr.id}-0",
            f"emr-{emr.id}-1",
            legacy_procedure.id,
        ]
        assert [item["source"] for item in procedures_payload["items"]] == [
            "emr",
            "emr",
            "legacy",
        ]
        assert procedures_payload["items"][0]["procedure_type"] == "Мезотерапия"
        assert procedures_payload["items"][0]["area_treated"] == "Лицо"
        assert procedures_payload["items"][0]["follow_up"] == "Контроль 14 дней"
        assert procedures_payload["items"][1]["procedure_type"] == "Чистка"
        assert procedures_payload["items"][0]["total_cost"] is None
        assert procedures_payload["items"][2]["total_cost"] == 99000
        assert procedures_payload["items"][2]["procedure_type"] == "legacy peel"

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

        exams_response = client.get(
            "/api/v1/derma/examinations?size=20", headers=headers
        )
        assert exams_response.status_code == 200
        exams_payload = exams_response.json()
        exam_ids = {item["id"] for item in exams_payload["items"]}
        assert f"emr-{emr_own.id}" in exam_ids
        assert f"emr-{emr_other.id}" not in exam_ids
        assert {item["patient_id"] for item in exams_payload["items"]} == {
            own_patient.id
        }

        procedures_response = client.get(
            "/api/v1/derma/procedures?size=20", headers=headers
        )
        assert procedures_response.status_code == 200
        procedures_payload = procedures_response.json()
        procedure_ids = {item["id"] for item in procedures_payload["items"]}
        assert f"emr-{emr_own.id}-0" in procedure_ids
        assert f"emr-{emr_other.id}-0" not in procedure_ids
        assert {item["patient_id"] for item in procedures_payload["items"]} == {
            own_patient.id
        }

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
        мусорные записи процедур не создают строк истории; total честно
        отражает отсутствие EMR-строк."""
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
                    "cosmetic_procedures": [{"procedure_type": "   "}],
                },
            },
        )

        exams_response = client.get(
            f"/api/v1/derma/examinations?patient_id={test_patient.id}&size=10",
            headers=auth_headers,
        )
        assert exams_response.status_code == 200
        exams_payload = exams_response.json()
        assert all(
            not str(item["id"]).startswith("emr-") for item in exams_payload["items"]
        )

        procedures_response = client.get(
            f"/api/v1/derma/procedures?patient_id={test_patient.id}&size=10",
            headers=auth_headers,
        )
        assert procedures_response.status_code == 200
        procedures_payload = procedures_response.json()
        assert procedures_payload["items"] == []
        assert procedures_payload["total"] == 0
        assert procedures_payload["pages"] == 0

    def test_history_is_complete_beyond_former_caps(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
        admin_user,
    ):
        """P2-4b regression pin (review P1 on #3490/#3491): the union must be
        complete — neither the former client-side limits (20 EMR summaries /
        10 legacy rows of #3490) nor a recency scan cap (500 candidates of
        #3491) may silently drop history. 505 dermatology EMRs must yield
        total=505, and the oldest rows must stay reachable on the last page."""
        records_count = 505
        size = 100

        visits = [
            Visit(
                patient_id=test_patient.id,
                doctor_id=test_doctor.id,
                visit_date=date.today() - timedelta(days=offset),
                status="open",
                source="desk",
                department="dermatology",
            )
            for offset in range(records_count)
        ]
        db_session.add_all(visits)
        db_session.flush()

        emr_rows = [
            EMRRecord(
                patient_id=test_patient.id,
                visit_id=visit.id,
                version=1,
                status="draft",
                created_by=admin_user.id,
                data={
                    "specialty": "dermatology",
                    "diagnosis": {"main": "Розацеа", "secondary": []},
                    "specialty_data": {
                        "skin_type": "combination",
                        "cosmetic_procedures": [
                            {
                                "procedure_date": (
                                    date.today() - timedelta(days=offset)
                                ).isoformat(),
                                "procedure_type": f"Процедура {offset}",
                            }
                        ],
                    },
                },
            )
            for offset, visit in enumerate(visits)
        ]
        db_session.add_all(emr_rows)
        db_session.commit()

        first_page = client.get(
            f"/api/v1/derma/examinations?patient_id={test_patient.id}"
            f"&page=1&size={size}",
            headers=auth_headers,
        )
        assert first_page.status_code == 200
        first_payload = first_page.json()
        assert first_payload["total"] == records_count
        assert first_payload["pages"] == 6  # ceil(505/100)
        assert len(first_payload["items"]) == size
        # newest first: the newest visit (today) opens the first page
        assert first_payload["items"][0]["examination_date"] == date.today().isoformat()

        last_page = client.get(
            f"/api/v1/derma/examinations?patient_id={test_patient.id}"
            f"&page=6&size={size}",
            headers=auth_headers,
        )
        assert last_page.status_code == 200
        last_payload = last_page.json()
        assert last_payload["total"] == records_count
        assert len(last_payload["items"]) == 5
        # the oldest rows (beyond the former 500-candidate window) survive
        oldest_dates = [
            item["examination_date"] for item in last_payload["items"]
        ]
        assert max(oldest_dates) == (date.today() - timedelta(days=500)).isoformat()
        assert min(oldest_dates) == (date.today() - timedelta(days=504)).isoformat()

        procedures_last_page = client.get(
            f"/api/v1/derma/procedures?patient_id={test_patient.id}"
            f"&page=6&size={size}",
            headers=auth_headers,
        )
        assert procedures_last_page.status_code == 200
        procedures_payload = procedures_last_page.json()
        assert procedures_payload["total"] == records_count
        assert len(procedures_payload["items"]) == 5
        assert procedures_payload["items"][0]["procedure_type"] == "Процедура 500"

    def test_history_pagination_envelope_is_exact(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
        admin_user,
    ):
        """P2-4b: канонический конверт пагинации — total/pages стабильны на
        всех страницах, срез (page-1)*size..page*size, страница за пределами
        диапазона возвращает пустые items без потери total."""
        seeded_exams = [
            DermaExamination(
                patient_id=test_patient.id,
                visit_id=None,
                doctor_id=admin_user.id,
                examination_date=date.today() - timedelta(days=offset),
                skin_type="combination",
                diagnosis=f"diagnosis {offset}",
            )
            for offset in range(5)
        ]
        db_session.add_all(seeded_exams)
        db_session.commit()

        for page, expected_ids in (
            (1, [0, 1]),
            (2, [2, 3]),
            (3, [4]),
            (4, []),
        ):
            response = client.get(
                f"/api/v1/derma/examinations?patient_id={test_patient.id}"
                f"&page={page}&size=2",
                headers=auth_headers,
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["total"] == 5
            assert payload["pages"] == 3
            assert payload["page"] == page
            assert payload["size"] == 2
            assert [item["id"] for item in payload["items"]] == [
                seeded_exams[offset].id for offset in expected_ids
            ]


@pytest.mark.integration
class TestDermaP3PhaseCSingleKeyApi:
    """P3 decision on the #3490/#3491 reconciliation, Phase C: the single
    canonical write/read key for derma procedures is
    specialty_data.cosmetic_procedures. Phase A projected the legacy key
    specialty_data.procedures as a transitional READ alias; Phase C removed
    the alias — rows under the legacy key are no longer projected (the
    write boundary in emr_contract.normalize_emr_data moves a saving
    client's legacy entries into the canonical key, and Phase B
    (scripts/audit_derma_legacy_procedures.py) guarantees no clinical data
    remains under the legacy key in active records before Phase C ships)."""

    def test_p3c_only_canonical_key_entries_visible(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
        admin_user,
    ):
        """Both keys in ONE record (external write past the save boundary):
        only the VALID canonical entries are projected — legacy entries are
        not read anymore, invalid canonical entries are skipped without
        hiding the rest."""
        visit = _create_visit(db_session, patient=test_patient, doctor=test_doctor)
        today = date.today().isoformat()
        canonical_entry = {
            "procedure_date": today,
            "procedure_type": "Мезотерапия",
            "area_treated": "Лицо",
            "products_used": "HA gel",
            "results": "Гиперемия слабая",
            "follow_up": "Контроль 14 дней",
        }
        emr = _create_emr(
            db_session,
            patient=test_patient,
            visit=visit,
            user=admin_user,
            data={
                "specialty": "dermatology",
                "specialty_data": {
                    "cosmetic_procedures": [
                        canonical_entry,  # canonical[0]: entry A
                        {  # canonical[1]: entry B
                            "procedure_date": today,
                            "procedure_type": "Чистка",
                            "area_treated": "Лоб",
                        },
                        {"procedure_type": "   "},  # blank type -> skip
                    ],
                    "procedures": [
                        dict(canonical_entry),  # legacy: NOT projected (Phase C)
                        {
                            "procedure_date": today,
                            "procedure_type": "Ботокс",
                            "area_treated": "Лоб",
                        },
                    ],
                },
            },
        )

        response = client.get(
            f"/api/v1/derma/procedures?patient_id={test_patient.id}&size=50",
            headers=auth_headers,
        )
        assert response.status_code == 200
        payload = response.json()
        # A + B only: the alias is gone, invalid canonical entries skipped.
        assert payload["total"] == 2
        row_ids = {item["id"] for item in payload["items"]}
        assert row_ids == {
            f"emr-{emr.id}-0",  # canonical A
            f"emr-{emr.id}-1",  # canonical B
        }
        assert not any("-legacy-" in item["id"] for item in payload["items"])
        types = sorted(item["procedure_type"] for item in payload["items"])
        assert types == sorted(["Мезотерапия", "Чистка"])
        # Every row stays bound to its record and visit.
        assert all(item["visit_id"] == visit.id for item in payload["items"])
        assert all(item["total_cost"] is None for item in payload["items"])

    def test_p3c_legacy_only_external_record_not_visible(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
        admin_user,
    ):
        """A record written by an external tool with entries ONLY under the
        legacy key surfaces nothing in /derma/procedures — this is exactly
        why Phase C ships strictly after the Phase B verify gate. The
        canonical editor-shaped record next to it stays fully visible with
        honest totals."""
        legacy_visit = _create_visit(
            db_session, patient=test_patient, doctor=test_doctor
        )
        _create_emr(
            db_session,
            patient=test_patient,
            visit=legacy_visit,
            user=admin_user,
            data={
                "specialty": "dermatology",
                "specialty_data": {
                    "procedures": [
                        {
                            "procedure_date": date.today().isoformat(),
                            "procedure_type": "Дарсонваль",
                            "area_treated": "Спина",
                        },
                    ],
                },
            },
        )
        canonical_visit = _create_visit(
            db_session, patient=test_patient, doctor=test_doctor
        )
        canonical_emr = _create_emr(
            db_session,
            patient=test_patient,
            visit=canonical_visit,
            user=admin_user,
            data=_derma_emr_data(),  # canonical key only (editor shape)
        )

        response = client.get(
            f"/api/v1/derma/procedures?patient_id={test_patient.id}&size=50",
            headers=auth_headers,
        )
        assert response.status_code == 200
        payload = response.json()
        # Only the 2 canonical entries of _derma_emr_data().
        assert payload["total"] == 2
        row_ids = {item["id"] for item in payload["items"]}
        assert row_ids == {
            f"emr-{canonical_emr.id}-0",
            f"emr-{canonical_emr.id}-1",
        }
        assert not any("-legacy-" in item["id"] for item in payload["items"])

    def test_garbage_key_shapes_yield_no_rows_and_honest_total(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
        admin_user,
    ):
        """Non-list arrays, empty arrays and entries without a usable type
        produce zero rows; total/pages stay honest."""
        # NB: emr_records.visit_id is UNIQUE — one EMR per visit.
        first_visit = _create_visit(db_session, patient=test_patient, doctor=test_doctor)
        _create_emr(
            db_session,
            patient=test_patient,
            visit=first_visit,
            user=admin_user,
            data={
                "specialty": "dermatology",
                "specialty_data": {
                    "cosmetic_procedures": [],
                    "procedures": "not-a-list",
                },
            },
        )
        second_visit = _create_visit(db_session, patient=test_patient, doctor=test_doctor)
        _create_emr(
            db_session,
            patient=test_patient,
            visit=second_visit,
            user=admin_user,
            data={
                "specialty": "dermatology",
                "specialty_data": {
                    "cosmetic_procedures": [
                        {"area_treated": "no type here"},  # no usable type
                        42,  # not a dict
                    ],
                },
            },
        )

        response = client.get(
            f"/api/v1/derma/procedures?patient_id={test_patient.id}&size=10",
            headers=auth_headers,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["items"] == []
        assert payload["total"] == 0
        assert payload["pages"] == 0

    def test_p3c_similar_canonical_entries_are_not_collapsed(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
        admin_user,
    ):
        """No content-based hiding at all (review P2), single-key edition:
        canonical entries that differ by leading/trailing whitespace only,
        by internal text, by letter case or by punctuation are ALL
        projected — the read path runs no normalization and no similarity
        judgment, so no variant of an entry can be silently folded away.
        Case and punctuation are additionally pinned verbatim in the
        projection. (Resolving genuinely double-written duplicates is
        Phase B territory — audit + operator-driven normalize — never the
        read path.)"""
        visit = _create_visit(db_session, patient=test_patient, doctor=test_doctor)
        today = date.today().isoformat()
        canonical_entry = {
            "procedure_date": today,
            "procedure_type": "Мезотерапия",
            "area_treated": "Лицо",
            "products_used": "HA gel",
            "results": "Гиперемия слабая",
            "follow_up": "Контроль 14 дней",
        }
        emr = _create_emr(
            db_session,
            patient=test_patient,
            visit=visit,
            user=admin_user,
            data={
                "specialty": "dermatology",
                "specialty_data": {
                    "cosmetic_procedures": [
                        canonical_entry,  # [0]: entry A
                        {  # [1]: edge-whitespace-only variant of A -> visible
                            "procedure_date": f"  {today}  ",
                            "procedure_type": "  Мезотерапия ",
                            "area_treated": " Лицо ",
                            "products_used": " HA gel  ",
                            "results": "  Гиперемия слабая   ",
                            "follow_up": " Контроль 14 дней ",
                        },
                        {  # [2]: INTERNAL text change -> visible
                            **canonical_entry,
                            "results": "Гиперемия выраженная",
                        },
                        {  # [3]: letter-case change -> visible (no case folding)
                            **canonical_entry,
                            "procedure_type": "мезотерапия",
                        },
                        {  # [4]: punctuation change -> visible (no folding)
                            **canonical_entry,
                            "follow_up": "Контроль 14 дней.",
                        },
                    ],
                },
            },
        )

        response = client.get(
            f"/api/v1/derma/procedures?patient_id={test_patient.id}&size=50",
            headers=auth_headers,
        )
        assert response.status_code == 200
        payload = response.json()
        # A + ALL FOUR variants — nothing is collapsed.
        assert payload["total"] == 5
        row_ids = {item["id"] for item in payload["items"]}
        assert row_ids == {
            f"emr-{emr.id}-0",  # A
            f"emr-{emr.id}-1",  # whitespace variant stays visible
            f"emr-{emr.id}-2",  # internal text change stays visible
            f"emr-{emr.id}-3",  # case change stays visible
            f"emr-{emr.id}-4",  # punctuation change stays visible
        }
        # Case is preserved verbatim in the projection: both spellings appear.
        types = [item["procedure_type"] for item in payload["items"]]
        assert types.count("Мезотерапия") == 3  # A + [2] + [4]
        assert types.count("  Мезотерапия ") == 1  # whitespace variant, verbatim
        assert types.count("мезотерапия") == 1  # lowercase row is NOT folded away
        # The internal text change is readable in its own row.
        by_id = {item["id"]: item for item in payload["items"]}
        assert by_id[f"emr-{emr.id}-2"]["results"] == "Гиперемия выраженная"
        assert by_id[f"emr-{emr.id}-4"]["follow_up"] == "Контроль 14 дней."
