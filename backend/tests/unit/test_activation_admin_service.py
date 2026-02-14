from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services.activation_admin_service import ActivationAdminService


@pytest.mark.unit
class TestActivationAdminService:
    def test_list_activations_maps_rows(self):
        row = SimpleNamespace(
            key="ABC",
            machine_hash="mh",
            expiry_date=datetime(2026, 1, 10),
            status="active",
            created_at=datetime(2026, 1, 1, 10, 0, 0),
            updated_at=datetime(2026, 1, 2, 10, 0, 0),
            meta='{"x": 1}',
        )
        repository = SimpleNamespace(
            list_activations=lambda **kwargs: ([row], 1),
        )
        service = ActivationAdminService(db=None, repository=repository)

        items, total = service.list_activations(
            status=None,
            key_like=None,
            machine_hash=None,
            limit=100,
            offset=0,
        )

        assert total == 1
        assert items[0].key == "ABC"
        assert items[0].status == "active"

    def test_revoke_returns_false_when_missing(self):
        repository = SimpleNamespace(get_by_key=lambda key: None)
        service = ActivationAdminService(db=None, repository=repository)

        assert service.revoke(key="missing") is False
