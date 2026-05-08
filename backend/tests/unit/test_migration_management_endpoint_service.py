from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.services.migration_management_endpoint_service import MigrationManagementEndpointService


@pytest.mark.unit
class TestMigrationManagementEndpointService:
    def test_parse_date_handles_none_and_iso_date(self):
        assert MigrationManagementEndpointService.parse_date(None) is None
        assert MigrationManagementEndpointService.parse_date("2026-02-14") == date(2026, 2, 14)

    def test_backup_queue_data_parses_date_before_delegating(self):
        captured: dict = {}

        class FakeMigrationService:
            def __init__(self, db):
                self.db = db

            def backup_queue_data(self, parsed_date):
                captured["parsed_date"] = parsed_date
                return {"success": True}

        service = MigrationManagementEndpointService(
            db=object(),
            repository=SimpleNamespace(),
            migration_service_factory=FakeMigrationService,
        )

        result = service.backup_queue_data("2026-01-31")

        assert result["success"] is True
        assert captured["parsed_date"] == date(2026, 1, 31)

    def test_get_migration_stats_maps_repository_rows(self):
        repository = SimpleNamespace(
            get_queue_stats=lambda: SimpleNamespace(
                total_queues=10,
                active_queues=4,
                opened_queues=2,
                earliest_date="2026-01-01",
                latest_date="2026-02-14",
            ),
            get_entry_stats=lambda: SimpleNamespace(
                total_entries=50,
                waiting_entries=20,
                called_entries=10,
                served_entries=15,
                linked_to_visits=30,
                migrated_entries=5,
            ),
            get_source_stats=lambda: [SimpleNamespace(source="online", count=12)],
            get_tag_stats=lambda: [
                SimpleNamespace(queue_tag="cardio", queue_count=3, total_entries=9)
            ],
        )
        service = MigrationManagementEndpointService(
            db=None,
            repository=repository,
            migration_service_factory=lambda db: SimpleNamespace(),
        )

        stats = service.get_migration_stats()

        assert stats["queue_statistics"]["total_queues"] == 10
        assert stats["entry_statistics"]["migrated_entries"] == 5
        assert stats["source_distribution"] == [{"source": "online", "count": 12}]
        assert stats["queue_tag_distribution"][0]["queue_tag"] == "cardio"

    def test_migrate_legacy_emr_data_delegates_to_cutover_service(self):
        class FakeEMRCutoverService:
            def __init__(self, db):
                self.db = db

            def migrate_legacy_emrs(self, *, limit, dry_run):
                return {"success": True, "limit": limit, "dry_run": dry_run}

        service = MigrationManagementEndpointService(
            db=object(),
            repository=SimpleNamespace(),
            migration_service_factory=lambda db: SimpleNamespace(),
            emr_cutover_service_factory=FakeEMRCutoverService,
        )

        result = service.migrate_legacy_emr_data(limit=25, dry_run=True)

        assert result == {"success": True, "limit": 25, "dry_run": True}

    def test_verify_emr_cutover_delegates_to_cutover_service(self):
        class FakeEMRCutoverService:
            def __init__(self, db):
                self.db = db

            def verify_cutover(self):
                return {"passed": True, "checks": {}, "generated_at": "2026-03-19T00:00:00"}

        service = MigrationManagementEndpointService(
            db=object(),
            repository=SimpleNamespace(),
            migration_service_factory=lambda db: SimpleNamespace(),
            emr_cutover_service_factory=FakeEMRCutoverService,
        )

        result = service.verify_emr_cutover()

        assert result["passed"] is True
        assert result["checks"] == {}

    def test_check_migration_health_marks_failed_checks(self):
        def get_count(table):
            if table == "queue_entries":
                raise RuntimeError("table missing")
            return 1

        repository = SimpleNamespace(
            get_table_record_count=get_count,
            get_queue_indexes=lambda: [SimpleNamespace(name="ix_queue_a")],
            get_alembic_revision=lambda: SimpleNamespace(version_num="0001_baseline"),
        )
        service = MigrationManagementEndpointService(
            db=None,
            repository=repository,
            migration_service_factory=lambda db: SimpleNamespace(),
        )

        health = service.check_migration_health()

        assert health["healthy"] is False
        assert health["checks"]["table_daily_queues"]["exists"] is True
        assert health["checks"]["table_queue_entries"]["exists"] is False
        assert "error" in health["checks"]["table_queue_entries"]
