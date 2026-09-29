from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models.visit import Visit


@pytest.mark.integration
class TestVisitsRescheduleAliases:
    def _make_visit(self, db_session, test_patient, test_doctor):
        visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=date.today(),
            status="open",
            source="desk",
        )
        db_session.add(visit)
        db_session.commit()
        db_session.refresh(visit)
        return visit

    @pytest.mark.parametrize(
        "path_template, params, expected_date",
        [
            (
                "/api/v1/visits/visits/{visit_id}/reschedule/tomorrow",
                None,
                date.today() + timedelta(days=1),
            ),
            (
                "/api/v1/visits/{visit_id}/reschedule/tomorrow",
                None,
                date.today() + timedelta(days=1),
            ),
            (
                "/api/v1/visits/visits/{visit_id}/reschedule",
                {"new_date": (date.today() + timedelta(days=3)).isoformat()},
                date.today() + timedelta(days=3),
            ),
            (
                "/api/v1/visits/{visit_id}/reschedule",
                {"new_date": (date.today() + timedelta(days=3)).isoformat()},
                date.today() + timedelta(days=3),
            ),
        ],
    )
    def test_reschedule_paths_support_canonical_and_legacy_aliases(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
        path_template,
        params,
        expected_date,
    ):
        visit = self._make_visit(db_session, test_patient, test_doctor)
        path = path_template.format(visit_id=visit.id)

        response = client.post(path, headers=auth_headers, params=params)

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["id"] == visit.id
        assert payload["patient_id"] == test_patient.id
        assert payload["doctor_id"] == test_doctor.id
        assert payload["status"] == "open"

        db_session.refresh(visit)
        assert visit.visit_date == expected_date

    @pytest.mark.parametrize(
        "reschedule_path_template",
        [
            "/api/v1/visits/visits/{visit_id}/reschedule",
            "/api/v1/visits/{visit_id}/reschedule",
        ],
    )
    def test_canceled_visit_is_removed_from_reschedule_happy_path(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
        reschedule_path_template,
    ):
        visit = self._make_visit(db_session, test_patient, test_doctor)

        cancel_response = client.post(
            f"/api/v1/visits/visits/{visit.id}/status",
            headers=auth_headers,
            params={"status_new": "canceled"},
        )
        assert cancel_response.status_code == 200, cancel_response.text
        assert cancel_response.json()["status"] == "canceled"

        db_session.refresh(visit)
        assert visit.status == "canceled"

        blocked_response = client.post(
            reschedule_path_template.format(visit_id=visit.id),
            headers=auth_headers,
            params={"new_date": (date.today() + timedelta(days=2)).isoformat()},
        )
        assert blocked_response.status_code == 409, blocked_response.text
        assert "canceled" in blocked_response.json()["detail"].lower()

    def test_reschedule_with_new_time_updates_visit_time(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
    ):
        """R-27 fix: reschedule with new_time should update visit_time."""
        visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=date.today(),
            visit_time="10:00",
            status="open",
            source="desk",
        )
        db_session.add(visit)
        db_session.commit()
        db_session.refresh(visit)

        response = client.post(
            f"/api/v1/visits/visits/{visit.id}/reschedule",
            headers=auth_headers,
            params={
                "new_date": (date.today() + timedelta(days=2)).isoformat(),
                "new_time": "14:30",
            },
        )

        assert response.status_code == 200, response.text
        db_session.refresh(visit)
        assert visit.visit_date == date.today() + timedelta(days=2)
        assert visit.visit_time == "14:30"

    def test_reschedule_without_new_time_preserves_visit_time(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
    ):
        """R-27 fix: reschedule without new_time should preserve existing visit_time."""
        visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=date.today(),
            visit_time="09:15",
            status="open",
            source="desk",
        )
        db_session.add(visit)
        db_session.commit()
        db_session.refresh(visit)

        response = client.post(
            f"/api/v1/visits/visits/{visit.id}/reschedule",
            headers=auth_headers,
            params={
                "new_date": (date.today() + timedelta(days=2)).isoformat(),
            },
        )

        assert response.status_code == 200, response.text
        db_session.refresh(visit)
        assert visit.visit_date == date.today() + timedelta(days=2)
        assert visit.visit_time == "09:15"  # preserved

    def test_reschedule_with_invalid_time_format_returns_422(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
    ):
        """R-27 fix: invalid new_time format should return 422."""
        visit = self._make_visit(db_session, test_patient, test_doctor)

        response = client.post(
            f"/api/v1/visits/visits/{visit.id}/reschedule",
            headers=auth_headers,
            params={
                "new_date": (date.today() + timedelta(days=2)).isoformat(),
                "new_time": "25:99",  # invalid
            },
        )

        assert response.status_code == 422, response.text
        assert "HH:MM" in response.json()["detail"]

    def _make_derm_history(
        self,
        db_session,
        test_patient,
        test_doctor,
        admin_user,
        *,
        visit_date,
    ):
        """Визит + дерма-ЭМК с осмотром: строки read model спроектированы."""
        from tests.integration.test_derma_history_read_model import (
            _add_emr,
            _add_visit,
            _derma_emr_data,
            _entries,
        )

        visit = _add_visit(
            db_session,
            patient=test_patient,
            doctor=test_doctor,
            visit_date=visit_date,
        )
        emr = _add_emr(
            db_session,
            visit=visit,
            data=_derma_emr_data(procedures=0, with_exam=True),
            created_by=admin_user.id,
        )
        entries = _entries(
            db_session, kind="examination", source="emr", record_id=emr.id
        )
        assert len(entries) == 1
        assert entries[0].entry_date == visit_date
        return visit, emr

    def test_reschedule_updates_derma_read_model(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
        admin_user,
    ):
        """P1 (owner fact-check 5625c8f1b, репро на SQLite): reschedule-роут
        пишет visit_date Core-UPDATE'ом по рефлектированной таблице —
        after_flush listener read model его не видит. Фикс: пересчёт строк
        визита в той же транзакции. дерма-ЭМК с осмотром на X, перенос на
        Y — entry_date/payload.examination_date и порядок GET /derma/*
        обязаны дать Y (прежде — старая дата и неверный порядок)."""
        from tests.integration.test_derma_history_read_model import (
            _entries,
        )

        # второй визит с более СТАРОЙ датой: после переноса первого в
        # будущее порядок GET /derma/* обязан перевернуться
        self._make_derm_history(
            db_session,
            test_patient,
            test_doctor,
            admin_user,
            visit_date=date.today() - timedelta(days=30),
        )
        visit, emr = self._make_derm_history(
            db_session,
            test_patient,
            test_doctor,
            admin_user,
            visit_date=date.today() - timedelta(days=5),
        )

        new_date = date.today() + timedelta(days=20)
        response = client.post(
            f"/api/v1/visits/visits/{visit.id}/reschedule",
            headers=auth_headers,
            params={"new_date": new_date.isoformat()},
        )
        assert response.status_code == 200, response.text

        # Core DELETE+INSERT не обновляет identity map сессии — перечитываем
        db_session.expire_all()
        entries = _entries(db_session, kind="examination", source="emr")
        assert len(entries) == 2
        moved = [e for e in entries if e.record_id == emr.id][0]
        assert moved.entry_date == new_date
        assert moved.payload["examination_date"] == new_date.isoformat()

        # живой эндпоинт: новая дата первой строкой (newest-first)
        derma = client.get(
            f"/api/v1/derma/examinations?patient_id={test_patient.id}"
            "&page=1&size=50",
            headers=auth_headers,
        )
        assert derma.status_code == 200, derma.text
        items = derma.json()["items"]
        assert items[0]["id"] == f"emr-{emr.id}"
        assert items[0]["examination_date"] == new_date.isoformat()

    def test_reschedule_tomorrow_updates_derma_read_model(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
        admin_user,
    ):
        """P1 (owner fact-check 5625c8f1b), второй независимый сайт записи:
        /reschedule/tomorrow — собственный Core-UPDATE в эндпоинте, не
        делегирует сервису. Досинхронизация обязательна и здесь."""
        from tests.integration.test_derma_history_read_model import (
            _entries,
        )

        visit, emr = self._make_derm_history(
            db_session,
            test_patient,
            test_doctor,
            admin_user,
            visit_date=date.today() - timedelta(days=5),
        )

        response = client.post(
            f"/api/v1/visits/visits/{visit.id}/reschedule/tomorrow",
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

        tomorrow = date.today() + timedelta(days=1)
        db_session.expire_all()
        entries = _entries(db_session, kind="examination", source="emr")
        assert len(entries) == 1
        assert entries[0].record_id == emr.id
        assert entries[0].entry_date == tomorrow
        assert entries[0].payload["examination_date"] == tomorrow.isoformat()
