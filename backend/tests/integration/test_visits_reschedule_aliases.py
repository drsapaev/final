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
