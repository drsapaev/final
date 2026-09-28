from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from app.models.derma_examination import DermaExamination
from app.models.derma_history import DermaHistoryEntry
from app.models.derma_procedure import DermaProcedure
from app.models.emr_v2 import EMRRecord
from app.models.visit import Visit

READ_MODEL_ORDER = (
    DermaHistoryEntry.entry_date.desc(),
    DermaHistoryEntry.created_at.desc(),
    DermaHistoryEntry.source.asc(),
    DermaHistoryEntry.record_id.desc(),
    DermaHistoryEntry.position.asc(),
)


def _suffix() -> str:
    return uuid4().hex[:10]


def _derma_emr_data(*, procedures: int = 2, with_exam: bool = True) -> dict:
    specialty_data: dict = {}
    if with_exam:
        specialty_data.update(
            {
                "skin_type": "combination",
                "skin_condition": "Чувствительная кожа",
                "treatment_plan": "Мягкий уход",
            }
        )
    if procedures:
        specialty_data["cosmetic_procedures"] = [
            {
                "procedure_date": date.today().isoformat(),
                "procedure_type": f"Процедура {index}",
                "area_treated": "Щёки",
            }
            for index in range(procedures)
        ]
    return {
        "specialty": "dermatology",
        "diagnosis": {"main": "Розацеа", "secondary": []},
        "specialty_data": specialty_data,
    }


def _entries(db_session, **filters) -> list[DermaHistoryEntry]:
    query = db_session.query(DermaHistoryEntry)
    for column, value in filters.items():
        query = query.filter(getattr(DermaHistoryEntry, column) == value)
    return query.order_by(*READ_MODEL_ORDER).all()


def _add_emr(db_session, *, visit, data, created_by, created_at=None):
    emr = EMRRecord(
        patient_id=visit.patient_id,
        visit_id=visit.id,
        version=1,
        status="draft",
        created_by=created_by,
        created_at=created_at or datetime.now(UTC),
        data=data,
    )
    db_session.add(emr)
    db_session.commit()
    db_session.refresh(emr)
    return emr


def _add_visit(db_session, *, patient, doctor, visit_date=None):
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


class TestDermaHistoryReadModelProjection:
    """Issue #3506, шаг 1: производная таблица обслуживается автоматически.

    Ключевой инвариант: любая ORM-запись источников (ЭМК, legacy, визит) —
    независимо от пути (сервис, cutover, прямой db_session.add в тестах) —
    поддерживает derma_history_entries в той же транзакции.
    """

    def test_emr_flush_projects_entries(
        self, db_session, test_patient, test_doctor, admin_user
    ):
        visit = _add_visit(
            db_session,
            patient=test_patient,
            doctor=test_doctor,
            visit_date=date.today() - timedelta(days=5),
        )
        emr = _add_emr(
            db_session,
            visit=visit,
            data=_derma_emr_data(procedures=2, with_exam=True),
            created_by=admin_user.id,
        )

        exams = _entries(db_session, kind="examination", source="emr")
        procs = _entries(db_session, kind="procedure", source="emr")
        assert len(exams) == 1
        assert len(procs) == 2

        exam_entry = exams[0]
        assert exam_entry.record_id == emr.id
        assert exam_entry.position == 0
        assert exam_entry.patient_id == test_patient.id
        assert exam_entry.visit_id == visit.id
        assert exam_entry.doctor_id == test_doctor.id
        assert exam_entry.entry_date == date.today() - timedelta(days=5)
        assert exam_entry.payload["id"] == f"emr-{emr.id}"
        assert exam_entry.payload["source"] == "emr"
        assert exam_entry.payload["skin_type"] == "combination"
        assert exam_entry.payload["diagnosis"] == "Розацеа"

        # порядок внутри записи = порядок массива (position asc)
        assert [e.position for e in procs] == [0, 1]
        assert [e.payload["procedure_type"] for e in procs] == [
            "Процедура 0",
            "Процедура 1",
        ]

    def test_non_derma_and_empty_emr_project_nothing(
        self, db_session, test_patient, test_doctor, admin_user
    ):
        visit_cardio = _add_visit(db_session, patient=test_patient, doctor=test_doctor)
        _add_emr(
            db_session,
            visit=visit_cardio,
            data={
                "specialty": "cardiology",
                "diagnosis": {"main": "Гипертония"},
                "specialty_data": {"skin_type": "combination"},
            },
            created_by=admin_user.id,
        )
        visit_empty = _add_visit(db_session, patient=test_patient, doctor=test_doctor)
        _add_emr(
            db_session,
            visit=visit_empty,
            data={
                "specialty": "dermatology",
                "specialty_data": {},  # пустой каркас — не история
            },
            created_by=admin_user.id,
        )
        assert _entries(db_session) == []

    def test_emr_update_replaces_entries_without_duplicates(
        self, db_session, test_patient, test_doctor, admin_user
    ):
        visit = _add_visit(db_session, patient=test_patient, doctor=test_doctor)
        emr = _add_emr(
            db_session,
            visit=visit,
            data=_derma_emr_data(procedures=1, with_exam=True),
            created_by=admin_user.id,
        )
        assert len(_entries(db_session, kind="procedure", source="emr")) == 1

        emr.data = _derma_emr_data(procedures=3, with_exam=True)
        db_session.commit()

        assert len(_entries(db_session, kind="examination", source="emr")) == 1
        procs = _entries(db_session, kind="procedure", source="emr")
        assert len(procs) == 3
        assert [e.position for e in procs] == [0, 1, 2]
        # уникальная идентичность (kind, source, record_id, position) держится
        identities = {
            (e.kind, e.source, e.record_id, e.position)
            for e in procs + _entries(db_session)
        }
        assert len(identities) == 4

    def test_emr_deactivation_removes_entries(
        self, db_session, test_patient, test_doctor, admin_user
    ):
        visit = _add_visit(db_session, patient=test_patient, doctor=test_doctor)
        emr = _add_emr(
            db_session,
            visit=visit,
            data=_derma_emr_data(),
            created_by=admin_user.id,
        )
        assert _entries(db_session, record_id=emr.id, source="emr")

        emr.is_active = False
        db_session.commit()
        assert _entries(db_session, record_id=emr.id, source="emr") == []

    def test_legacy_rows_project_and_delete(
        self, db_session, test_patient, test_doctor
    ):
        exam = DermaExamination(
            patient_id=test_patient.id,
            visit_id=None,
            doctor_id=test_doctor.id,
            examination_date=date.today() - timedelta(days=10),
            skin_type="dry",
            skin_condition="Шелушение",
        )
        proc = DermaProcedure(
            patient_id=test_patient.id,
            visit_id=None,
            doctor_id=test_doctor.id,
            procedure_date=date.today() - timedelta(days=9),
            procedure_type="Чистка",
        )
        db_session.add_all([exam, proc])
        db_session.commit()
        db_session.refresh(exam)
        db_session.refresh(proc)

        exam_entries = _entries(db_session, kind="examination", source="legacy")
        proc_entries = _entries(db_session, kind="procedure", source="legacy")
        assert len(exam_entries) == 1
        assert len(proc_entries) == 1
        assert exam_entries[0].record_id == exam.id
        assert exam_entries[0].payload["id"] == exam.id
        assert exam_entries[0].payload["source"] == "legacy"
        assert proc_entries[0].record_id == proc.id

        db_session.delete(proc)
        db_session.commit()
        assert _entries(db_session, kind="procedure", source="legacy") == []
        assert len(_entries(db_session, kind="examination", source="legacy")) == 1

    def test_visit_date_change_reprojects_entries(
        self, db_session, test_patient, test_doctor, admin_user
    ):
        visit = _add_visit(
            db_session,
            patient=test_patient,
            doctor=test_doctor,
            visit_date=date.today(),
        )
        _add_emr(
            db_session,
            visit=visit,
            data=_derma_emr_data(procedures=0, with_exam=True),
            created_by=admin_user.id,
        )
        assert _entries(db_session, kind="examination")[0].entry_date == date.today()

        visit.visit_date = date.today() + timedelta(days=30)
        db_session.commit()
        assert _entries(db_session, kind="examination")[
            0
        ].entry_date == date.today() + timedelta(days=30)

    def test_read_model_order_matches_endpoint(
        self, client, db_session, auth_headers, test_patient, test_doctor, admin_user
    ):
        """Паритет-пин контракта порядка (основа переключения PR 2).

        Выборка read model с каноническим ORDER BY обязана совпадать с
        фактическим порядком живого эндпоинта (in-memory мерж #3494):
        newest-first, при равенстве (date, created_at) EMR раньше legacy,
        внутри источника — порядок выборки, позиции числовые.
        """
        same_day = date.today() - timedelta(days=3)
        same_created = datetime.now(UTC) - timedelta(days=3)

        visit_emr = _add_visit(
            db_session, patient=test_patient, doctor=test_doctor, visit_date=same_day
        )
        emr = _add_emr(
            db_session,
            visit=visit_emr,
            data=_derma_emr_data(procedures=2, with_exam=True),
            created_by=admin_user.id,
            created_at=same_created,
        )
        legacy_same_day = DermaExamination(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            examination_date=same_day,
            skin_type="oily",
            created_at=same_created.replace(tzinfo=None),
        )
        legacy_older = DermaExamination(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            examination_date=date.today() - timedelta(days=30),
            skin_type="dry",
        )
        db_session.add_all([legacy_same_day, legacy_older])
        db_session.commit()

        for kind, path in (
            ("examination", "/api/v1/derma/examinations"),
            ("procedure", "/api/v1/derma/procedures"),
        ):
            response = client.get(
                f"{path}?patient_id={test_patient.id}&page=1&size=50",
                headers=auth_headers,
            )
            assert response.status_code == 200
            endpoint_ids = [item["id"] for item in response.json()["items"]]
            read_model_ids = [
                entry.payload["id"] for entry in _entries(db_session, kind=kind)
            ]
            assert read_model_ids == endpoint_ids

        # тай-брейк равенства дат: EMR раньше legacy
        exam_ids = [
            entry.payload["id"] for entry in _entries(db_session, kind="examination")
        ]
        assert exam_ids.index(f"emr-{emr.id}") < exam_ids.index(legacy_same_day.id)
        # процедуры записи идут в порядке массива
        proc_ids = [
            entry.payload["id"] for entry in _entries(db_session, kind="procedure")
        ]
        assert proc_ids == [f"emr-{emr.id}-0", f"emr-{emr.id}-1"]

    def test_505_records_project_completely(
        self, db_session, test_patient, test_doctor, admin_user
    ):
        """Перенос регрессионного пина полноты #3494 на read model."""
        records_count = 505
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
                    "diagnosis": {"main": "Розацеа"},
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

        exams = _entries(db_session, kind="examination", source="emr")
        procs = _entries(db_session, kind="procedure", source="emr")
        assert len(exams) == records_count
        assert len(procs) == records_count
        # newest first, старейшие записи доступны (бывший cap 500 превышен)
        assert exams[0].entry_date == date.today()
        assert exams[-1].entry_date == date.today() - timedelta(days=504)
        assert procs[-1].payload["procedure_type"] == "Процедура 504"

    def test_endpoint_read_volume_is_constant_across_pages(
        self, client, db_session, auth_headers, test_patient, test_doctor, admin_user
    ):
        """Issue #3506, шаг 2: объём чтения не растёт с глубиной истории.

        Бывший in-memory путь читал ВСЕ строки обоих источников на каждый
        запрос страницы (P2 ретро-ревью #3494). Read model обслуживает
        страницу фиксированным числом SQL-выражений (COUNT + срез) — пин:
        счётчик выражений на соединении одинаков для каждой страницы.
        """
        from sqlalchemy import event as sa_event

        records_count = 45  # 3 страницы по size=20
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
        db_session.add_all(
            [
                EMRRecord(
                    patient_id=test_patient.id,
                    visit_id=visit.id,
                    version=1,
                    status="draft",
                    created_by=admin_user.id,
                    data={
                        "specialty": "dermatology",
                        "diagnosis": {"main": "Розацеа"},
                        "specialty_data": {"skin_type": "combination"},
                    },
                )
                for visit in visits
            ]
        )
        db_session.commit()

        connection = db_session.get_bind()

        def _counted_get(page: int) -> tuple[int, int]:
            counter = {"n": 0}

            def _count(*_args, **_kwargs) -> None:
                counter["n"] += 1

            sa_event.listen(connection, "before_cursor_execute", _count)
            try:
                response = client.get(
                    f"/api/v1/derma/examinations?patient_id={test_patient.id}"
                    f"&page={page}&size=20",
                    headers=auth_headers,
                )
            finally:
                sa_event.remove(connection, "before_cursor_execute", _count)
            assert response.status_code == 200
            return counter["n"], response.json()["total"]

        # прогрев: разовая загрузка пользователя в сессию (не относится к
        # глубине истории) не должна попадать в замер
        warm = client.get(
            f"/api/v1/derma/examinations?patient_id={test_patient.id}"
            "&page=1&size=20",
            headers=auth_headers,
        )
        assert warm.status_code == 200

        counts = []
        for page in (1, 2, 3):
            statements, total = _counted_get(page)
            assert total == records_count
            counts.append(statements)
        assert counts[0] == counts[1] == counts[2], counts
