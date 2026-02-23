"""Service layer for migration_management endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from sqlalchemy.orm import Session

from app.repositories.migration_management_repository import MigrationManagementRepository
from app.services.migration_service import MigrationService


class MigrationManagementApiService:
    """Orchestrates migration actions and SQL-based health/statistics payloads."""

    def __init__(
        self,
        db: Session,
        repository: MigrationManagementRepository | None = None,
        migration_service_factory: Callable[[Session], MigrationService] | None = None,
    ):
        self.db = db
        self.repository = repository or MigrationManagementRepository(db)
        self._migration_service_factory = migration_service_factory or MigrationService

    def _migration_service(self) -> MigrationService:
        return self._migration_service_factory(self.db)

    @staticmethod
    def parse_date(value: str | None):
        if not value:
            return None
        return datetime.strptime(value, "%Y-%m-%d").date()

    def migrate_legacy_queue_data(self) -> dict:
        return self._migration_service().migrate_legacy_queue_data()

    def check_data_integrity(self) -> dict:
        return self._migration_service()._check_data_integrity()

    def backup_queue_data(self, target_date: str | None) -> dict:
        parsed_date = self.parse_date(target_date)
        return self._migration_service().backup_queue_data(parsed_date)

    def restore_queue_data(self, backup_file: str) -> dict:
        return self._migration_service().restore_queue_data(backup_file)

    def cleanup_old_data(self, days_to_keep: int) -> dict:
        return self._migration_service().cleanup_old_data(days_to_keep)

    def get_migration_stats(self) -> dict:
        queue_stats = self.repository.get_queue_stats()
        entry_stats = self.repository.get_entry_stats()
        source_stats = self.repository.get_source_stats()
        tag_stats = self.repository.get_tag_stats()

        return {
            "queue_statistics": {
                "total_queues": queue_stats.total_queues,
                "active_queues": queue_stats.active_queues,
                "opened_queues": queue_stats.opened_queues,
                "earliest_date": queue_stats.earliest_date,
                "latest_date": queue_stats.latest_date,
            },
            "entry_statistics": {
                "total_entries": entry_stats.total_entries,
                "waiting_entries": entry_stats.waiting_entries,
                "called_entries": entry_stats.called_entries,
                "served_entries": entry_stats.served_entries,
                "linked_to_visits": entry_stats.linked_to_visits,
                "migrated_entries": entry_stats.migrated_entries,
            },
            "source_distribution": [
                {"source": row.source, "count": row.count} for row in source_stats
            ],
            "queue_tag_distribution": [
                {
                    "queue_tag": row.queue_tag,
                    "queue_count": row.queue_count,
                    "total_entries": row.total_entries,
                }
                for row in tag_stats
            ],
            "generated_at": datetime.utcnow().isoformat(),
        }

    def check_migration_health(self) -> dict:
        health_checks: dict = {}
        tables_to_check = ["daily_queues", "queue_entries", "queue_tokens"]

        for table in tables_to_check:
            if not all(c.isalnum() or c == "_" for c in table):
                health_checks[f"table_{table}"] = {
                    "exists": False,
                    "error": "Invalid table name",
                }
                continue
            try:
                health_checks[f"table_{table}"] = {
                    "exists": True,
                    "record_count": self.repository.get_table_record_count(table),
                }
            except Exception as exc:  # noqa: BLE001
                health_checks[f"table_{table}"] = {"exists": False, "error": str(exc)}

        try:
            indexes = self.repository.get_queue_indexes()
            health_checks["indexes"] = {
                "count": len(indexes),
                "names": [idx.name for idx in indexes],
            }
        except Exception as exc:  # noqa: BLE001
            health_checks["indexes"] = {"error": str(exc)}

        try:
            current_revision = self.repository.get_alembic_revision()
            health_checks["alembic"] = {
                "current_revision": (
                    current_revision.version_num if current_revision else None
                )
            }
        except Exception as exc:  # noqa: BLE001
            health_checks["alembic"] = {"error": str(exc)}

        all_healthy = all(
            check.get("exists", True) and "error" not in check
            for check in health_checks.values()
        )

        return {
            "healthy": all_healthy,
            "checks": health_checks,
            "checked_at": datetime.utcnow().isoformat(),
        }

