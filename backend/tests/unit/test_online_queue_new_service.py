from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.online_queue_new_service import (
    OnlineQueueNewDomainError,
    OnlineQueueNewService,
)


@pytest.mark.unit
class TestOnlineQueueNewService:
    def test_cancel_entry_raises_if_not_found(self):
        repository = SimpleNamespace(get_entry=lambda entry_id: None)
        service = OnlineQueueNewService(db=None, repository=repository)

        with pytest.raises(OnlineQueueNewDomainError) as exc_info:
            service.cancel_entry(entry_id=10)

        assert exc_info.value.status_code == 404

    def test_cancel_entry_updates_status(self):
        entry = SimpleNamespace(id=1, status="waiting")
        repository = SimpleNamespace(
            get_entry=lambda entry_id: entry,
            update_entry_status=lambda entry, status: SimpleNamespace(
                id=entry.id,
                status=status,
            ),
        )
        service = OnlineQueueNewService(db=None, repository=repository)

        updated = service.cancel_entry(entry_id=1)

        assert updated.status == "canceled"

