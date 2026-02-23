from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.global_search_api_service import GlobalSearchApiService


@pytest.mark.unit
class TestGlobalSearchApiService:
    def test_search_patients_deduplicates_exact_and_fuzzy_results(self):
        patient = SimpleNamespace(
            id=1,
            first_name="A",
            last_name="B",
            middle_name=None,
            phone=None,
            birth_date=None,
        )

        class Repository:
            def get_patient(self, patient_id):
                return patient

            def search_patients(self, *, query, limit):
                return [patient]

        service = GlobalSearchApiService(db=None, repository=Repository())
        results = service.search_patients(query="1", limit=5)
        assert len(results) == 1
        assert results[0]["id"] == 1

    def test_log_search_click_returns_error_payload_on_exception(self):
        class Repository:
            def create_audit(self, **kwargs):
                raise RuntimeError("boom")

            def rollback(self):
                pass

        service = GlobalSearchApiService(db=None, repository=Repository())
        response = service.log_search_click(
            user=SimpleNamespace(id=1, role="Admin"),
            query="abc",
            opened_type="patient",
            opened_id=2,
        )
        assert response["status"] == "error"
