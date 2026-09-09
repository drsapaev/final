from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.online_queue_new_service import (
    OnlineQueueNewDomainError,
    OnlineQueueNewService,
)


class _FakeQuery:
    """Минимальная имитация query-цепочки: filter → with_for_update → first."""

    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self._result


class _FakeSession:
    def __init__(self, entry_result):
        self._entry_result = entry_result
        self.committed = False
        self.refreshed: list[object] = []

    def query(self, model):
        return _FakeQuery(self._entry_result)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        self.refreshed.append(obj)


@pytest.mark.unit
class TestOnlineQueueNewService:
    def test_cancel_entry_raises_if_not_found(self):
        # W2-PR3: несуществующая запись — доменная 404 (как и раньше),
        # но чтение теперь под блокировкой строки через сессию.
        service = OnlineQueueNewService(db=_FakeSession(None))

        with pytest.raises(OnlineQueueNewDomainError) as exc_info:
            service.cancel_entry(entry_id=10)

        assert exc_info.value.status_code == 404

    def test_cancel_entry_updates_status(self):
        # W2-PR3: запись без связанного визита отменяется флипом статуса
        # (легаси-поведение сохранено); коммит один, объект refreshed.
        # R14: каноническое написание статуса записи — «cancelled».
        entry = SimpleNamespace(id=1, status="waiting", visit_id=None)
        session = _FakeSession(entry)
        service = OnlineQueueNewService(db=session)

        updated = service.cancel_entry(entry_id=1)

        assert updated.status == "cancelled"
        assert session.committed is True
        assert session.refreshed == [entry]
