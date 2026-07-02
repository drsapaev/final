from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.admin_doctors_stats_service import AdminDoctorsStatsService


@pytest.mark.unit
class TestAdminDoctorsStatsService:
    def test_get_specialties_builds_payload(self):
        repository = SimpleNamespace(
            list_active_specialties=lambda: ["cardiology", "custom"],
            count_active_by_specialty=lambda specialty: 3 if specialty == "cardiology" else 1,
        )
        service = AdminDoctorsStatsService(db=None, repository=repository)

        result = service.get_specialties()

        assert len(result) == 2
        assert result[0]["code"] == "cardiology"
        assert result[0]["doctor_count"] == 3

    def test_get_doctors_stats_aggregates_counts(self):
        repository = SimpleNamespace(
            list_active_specialties=lambda: ["cardiology", "dermatology"],
            count_active_doctors=lambda: 5,
            count_active_by_specialty=lambda specialty: 3 if specialty == "cardiology" else 2,
        )
        service = AdminDoctorsStatsService(db=None, repository=repository)

        result = service.get_doctors_stats()

        assert result["total_doctors"] == 5
        assert result["by_specialty"]["cardiology"] == 3
        assert result["by_specialty"]["dermatology"] == 2

