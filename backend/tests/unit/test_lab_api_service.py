from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.lab_api_service import LabApiDomainError, LabApiService


@pytest.mark.unit
class TestLabApiService:
    def test_update_result_raises_when_order_missing(self):
        repository = SimpleNamespace(get_order=lambda req_id: None)
        service = LabApiService(db=None, repository=repository)

        with pytest.raises(LabApiDomainError) as exc_info:
            service.update_result(req_id=42, notes="x", status="done")

        assert exc_info.value.status_code == 404

    def test_update_result_calls_repository_update(self):
        order = SimpleNamespace(id=7, status="ordered", notes=None)
        repository = SimpleNamespace(
            get_order=lambda req_id: order,
            update_order_fields=lambda row, notes, status: SimpleNamespace(
                id=row.id,
                notes=notes,
                status=status,
            ),
        )
        service = LabApiService(db=None, repository=repository)

        result = service.update_result(req_id=7, notes="done", status="done")

        assert result.id == 7
        assert result.notes == "done"
        assert result.status == "done"

