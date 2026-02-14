from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.file_system_api_service import FileSystemApiService


@pytest.mark.unit
class TestFileSystemApiService:
    def test_count_files_delegates_to_repository(self):
        class Repository:
            def count_files(self, **kwargs):
                assert kwargs["owner_id"] == 1
                return 42

        service = FileSystemApiService(db=None, repository=Repository())
        result = service.count_files(
            file_model=object(),
            owner_id=1,
            file_type=None,
            patient_id=None,
            appointment_id=None,
            emr_id=None,
            folder_id=None,
        )

        assert result == 42

    def test_finalize_file_delete_audit_logs_and_commits(self, monkeypatch):
        calls = {"logged": False, "committed": False}

        class Repository:
            db = object()

            def commit(self):
                calls["committed"] = True

        def fake_log_critical_change(**kwargs):
            calls["logged"] = True
            assert kwargs["action"] == "DELETE"
            assert kwargs["row_id"] == 10

        monkeypatch.setattr(
            "app.services.file_system_api_service.log_critical_change",
            fake_log_critical_change,
        )

        service = FileSystemApiService(db=None, repository=Repository())
        service.finalize_file_delete_audit(
            request=SimpleNamespace(),
            user_id=1,
            file_id=10,
            old_data={"id": 10},
            filename="a.pdf",
        )

        assert calls["logged"] is True
        assert calls["committed"] is True
