"""Repository helpers for migration_management endpoints."""

from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session


class MigrationManagementRepository:
    """Encapsulates SQL stats and health-check queries for migration API."""

    def __init__(self, db: Session):
        self.db = db

    def get_queue_stats(self):
        return self.db.execute(
            text(
                """
                SELECT
                    COUNT(*) as total_queues,
                    COUNT(CASE WHEN active = 1 THEN 1 END) as active_queues,
                    COUNT(CASE WHEN opened_at IS NOT NULL THEN 1 END) as opened_queues,
                    MIN(day) as earliest_date,
                    MAX(day) as latest_date
                FROM daily_queues
                """
            )
        ).fetchone()

    def get_entry_stats(self):
        return self.db.execute(
            text(
                """
                SELECT
                    COUNT(*) as total_entries,
                    COUNT(CASE WHEN status = 'waiting' THEN 1 END) as waiting_entries,
                    COUNT(CASE WHEN status = 'called' THEN 1 END) as called_entries,
                    COUNT(CASE WHEN status = 'served' THEN 1 END) as served_entries,
                    COUNT(CASE WHEN visit_id IS NOT NULL THEN 1 END) as linked_to_visits,
                    COUNT(CASE WHEN source = 'migration' THEN 1 END) as migrated_entries
                FROM queue_entries
                """
            )
        ).fetchone()

    def get_source_stats(self):
        return self.db.execute(
            text(
                """
                SELECT
                    source,
                    COUNT(*) as count
                FROM queue_entries
                GROUP BY source
                ORDER BY count DESC
                """
            )
        ).fetchall()

    def get_tag_stats(self):
        return self.db.execute(
            text(
                """
                SELECT
                    queue_tag,
                    COUNT(*) as queue_count,
                    SUM((SELECT COUNT(*) FROM queue_entries WHERE queue_id = daily_queues.id)) as total_entries
                FROM daily_queues
                WHERE queue_tag IS NOT NULL
                GROUP BY queue_tag
                ORDER BY queue_count DESC
                """
            )
        ).fetchall()

    def get_table_record_count(self, table: str) -> int:
        return self.db.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()[0]

    def get_queue_indexes(self):
        inspector = inspect(self.db.get_bind())
        queue_tables = [
            table_name
            for table_name in inspector.get_table_names()
            if "queue" in table_name
        ]

        indexes: list[SimpleNamespace] = []
        for table_name in queue_tables:
            for idx in inspector.get_indexes(table_name):
                idx_name = idx.get("name")
                if idx_name and "queue" in idx_name:
                    indexes.append(SimpleNamespace(name=idx_name, table=table_name))
        return indexes

    def get_alembic_revision(self):
        return self.db.execute(
            text(
                """
                SELECT version_num FROM alembic_version
                """
            )
        ).fetchone()
