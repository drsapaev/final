"""
Юнит тесты для сервиса миграций
"""
import json
import os
import tempfile
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.visit import Visit
from app.services.migration_service import MigrationService


@pytest.mark.unit
@pytest.mark.migration
class TestMigrationService:
    """Тесты для MigrationService"""

    def test_migration_service_initialization(self, db_session):
        """Тест инициализации сервиса миграций"""
        service = MigrationService(db_session)

        assert service.db == db_session

    def test_get_specialist_for_department(self, db_session, cardio_user):
        """Тест получения специалиста для отделения"""
        service = MigrationService(db_session)

        specialist_id = service._get_specialist_for_department("cardiology")

        assert specialist_id == cardio_user.id

    def test_get_specialist_for_unknown_department(self, db_session):
        """Тест получения специалиста для неизвестного отделения"""
        service = MigrationService(db_session)

        specialist_id = service._get_specialist_for_department("unknown")

        assert specialist_id is None

    def test_get_queue_tag_for_department(self, db_session):
        """Тест получения тега очереди для отделения"""
        service = MigrationService(db_session)

        tag = service._get_queue_tag_for_department("cardiology")
        assert tag == "cardiology_common"

        tag = service._get_queue_tag_for_department("dermatology")
        assert tag == "dermatology"

        tag = service._get_queue_tag_for_department("unknown")
        assert tag == "general"

    def test_get_or_create_daily_queue_existing(self, db_session, test_daily_queue):
        """Тест получения существующей дневной очереди"""
        service = MigrationService(db_session)

        queue = service._get_or_create_daily_queue(
            day=test_daily_queue.day,
            specialist_id=test_daily_queue.specialist_id,
            queue_tag=test_daily_queue.queue_tag
        )

        assert queue.id == test_daily_queue.id

    def test_get_or_create_daily_queue_new(self, db_session, cardio_user):
        """Тест создания новой дневной очереди"""
        service = MigrationService(db_session)

        queue = service._get_or_create_daily_queue(
            day=date.today(),
            specialist_id=cardio_user.id,
            queue_tag="new_queue_tag"
        )

        assert queue.id is not None
        assert queue.day == date.today()
        assert queue.specialist_id == cardio_user.id
        assert queue.queue_tag == "new_queue_tag"

    def test_map_old_status_to_new(self, db_session):
        """Тест маппинга старых статусов в новые"""
        service = MigrationService(db_session)

        assert service._map_old_status_to_new("waiting") == "waiting"
        assert service._map_old_status_to_new("called") == "called"
        assert service._map_old_status_to_new("completed") == "served"
        assert service._map_old_status_to_new("cancelled") == "no_show"
        assert service._map_old_status_to_new("unknown") == "waiting"

    def test_check_data_integrity_empty_db(self, db_session):
        """Тест проверки целостности данных в пустой БД"""
        service = MigrationService(db_session)

        result = service._check_data_integrity()

        assert result["passed"] is True
        assert "checks" in result
        assert "checked_at" in result
        assert result["checks"]["duplicate_numbers"]["passed"] is True
        assert result["checks"]["orphaned_visits"]["passed"] is True

    def test_check_data_integrity_with_data(self, db_session, test_queue_entry):
        """Тест проверки целостности данных с существующими данными"""
        service = MigrationService(db_session)

        result = service._check_data_integrity()

        assert result["passed"] is True
        assert "checks" in result

    def test_backup_queue_data_empty(self, db_session):
        """Тест создания резервной копии пустых данных"""
        service = MigrationService(db_session)

        with patch('os.makedirs'), patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            result = service.backup_queue_data(date.today())

            assert result["success"] is True
            assert result["queues_count"] == 0
            assert result["total_entries"] == 0
            assert "backup_file" in result

    def test_backup_queue_data_with_data(self, db_session, test_daily_queue, test_queue_entry):
        """Тест создания резервной копии с данными"""
        # SSOT: бэкапим очередь дня КЛИНИКИ (фикстуры сеются clinic-today)
        service = MigrationService(db_session)

        with patch('os.makedirs'), patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            result = service.backup_queue_data(test_daily_queue.day)

            assert result["success"] is True
            assert result["queues_count"] == 1
            assert result["total_entries"] == 1

    def test_backup_queue_data_error_handling(self, db_session):
        """Тест обработки ошибок при создании резервной копии"""
        service = MigrationService(db_session)

        with patch('os.makedirs', side_effect=Exception("Test error")):
            result = service.backup_queue_data(date.today())

            assert result["success"] is False
            assert "error" in result

    def test_restore_queue_data_success(self, db_session):
        """Тест успешного восстановления данных"""
        service = MigrationService(db_session)

        # Создаем тестовые данные для восстановления
        backup_data = {
            "backup_date": date.today().isoformat(),
            "created_at": datetime.utcnow().isoformat(),
            "queues": [{
                "id": 999,
                "day": date.today().isoformat(),
                "specialist_id": 1,
                "queue_tag": "test_queue",
                "active": True,
                "opened_at": None,
                "entries": [{
                    "id": 999,
                    "number": 1,
                    "patient_id": None,
                    "patient_name": "Test Patient",
                    "phone": "+998900000121",
                    "telegram_id": None,
                    "visit_id": None,
                    "source": "test",
                    "status": "waiting",
                    "created_at": datetime.utcnow().isoformat(),
                    "called_at": None
                }]
            }]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(backup_data, f)
            backup_file = f.name

        try:
            result = service.restore_queue_data(backup_file)

            assert result["success"] is True
            assert result["restored_queues"] == 1
            assert result["restored_entries"] == 1

            # Проверяем что данные действительно восстановились
            queue = db_session.query(DailyQueue).filter(DailyQueue.id == 999).first()
            assert queue is not None
            assert queue.queue_tag == "test_queue"

        finally:
            os.unlink(backup_file)

    def test_restore_queue_data_file_not_found(self, db_session):
        """Тест восстановления из несуществующего файла"""
        service = MigrationService(db_session)

        result = service.restore_queue_data("nonexistent_file.json")

        assert result["success"] is False
        assert "error" in result

    def test_cleanup_old_data_empty(self, db_session):
        """Тест очистки старых данных в пустой БД"""
        service = MigrationService(db_session)

        result = service.cleanup_old_data(days_to_keep=30)

        assert result["success"] is True
        assert result["deleted_queues"] == 0
        assert result["deleted_entries"] == 0

    def test_cleanup_old_data_with_old_data(self, db_session, cardio_user):
        """Тест очистки старых данных"""
        # Создаем старую очередь
        old_date = date.today() - timedelta(days=40)
        old_queue = DailyQueue(
            day=old_date,
            specialist_id=cardio_user.id,
            queue_tag="old_queue",
            active=False
        )
        db_session.add(old_queue)
        db_session.commit()

        service = MigrationService(db_session)

        result = service.cleanup_old_data(days_to_keep=30)

        assert result["success"] is True
        assert result["deleted_queues"] >= 1

    def test_cleanup_old_data_error_handling(self, db_session):
        """Тест обработки ошибок при очистке данных"""
        service = MigrationService(db_session)

        with patch.object(db_session, 'query', side_effect=Exception("Test error")):
            result = service.cleanup_old_data(days_to_keep=30)

            assert result["success"] is False
            assert "error" in result

    @patch('app.services.migration_service.logger')
    def test_logging_migration_events(self, mock_logger, db_session):
        """Тест логирования событий миграции"""
        service = MigrationService(db_session)

        service.cleanup_old_data(days_to_keep=30)

        # Проверяем что логирование вызывалось
        assert mock_logger.info.called

    def test_migrate_legacy_queue_data_no_old_table(self, db_session):
        """Тест миграции когда старая таблица не существует"""
        service = MigrationService(db_session)

        result = service.migrate_legacy_queue_data()

        assert result["success"] is True
        assert result["migrated_records"] == 0
        assert len(result["errors"]) == 0

    @patch('app.services.migration_service.logger')
    def test_error_logging(self, mock_logger, db_session):
        """Тест логирования ошибок"""
        service = MigrationService(db_session)

        # Вызываем метод который может вызвать ошибку
        with patch.object(service, '_check_data_integrity', side_effect=Exception("Test error")):
            result = service.migrate_legacy_queue_data()

            assert result["success"] is False
            assert mock_logger.error.called

    def test_backup_restore_roundtrip_preserves_start_number(
        self, db_session, cardio_user, tmp_path, monkeypatch
    ):
        """R19 P2 (snapshot survives the backup): the backup format must
        carry the day's frozen start_number (RQ-13.b D-06 snapshot) and
        the restore must put it back. A restored otherwise-empty queue
        used to silently fall back to the column default (1): ordinary
        numbering then read the restored row as a snapshot-1 day instead
        of the saved 41."""
        from app.crud.clinic import clinic_today
        from app.services.queue_service import queue_service

        queue = DailyQueue(
            day=clinic_today(db_session),
            specialist_id=cardio_user.id,
            queue_resource_id=None,
            queue_tag="r19_roundtrip",
            active=True,
            start_number=41,
        )
        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)
        queue_id = queue.id

        monkeypatch.chdir(tmp_path)
        service = MigrationService(db_session)

        backup_result = service.backup_queue_data(queue.day)
        assert backup_result["success"] is True, backup_result

        with open(backup_result["backup_file"], encoding="utf-8") as f:
            payload = json.load(f)
        exported = next(q for q in payload["queues"] if q["id"] == queue_id)
        assert exported.get("start_number") == 41, (
            "backup must serialize the day's frozen start_number"
        )

        # restore into a DB where the original row is absent
        db_session.delete(queue)
        db_session.commit()

        try:
            restore_result = service.restore_queue_data(
                str(tmp_path / backup_result["backup_file"])
            )
            assert restore_result["success"] is True, restore_result

            restored = (
                db_session.query(DailyQueue).filter(DailyQueue.id == queue_id).first()
            )
            assert restored is not None
            assert restored.start_number == 41, (
                "restore must put the recorded snapshot back without "
                "recalculation (got the column default?)"
            )
            # the next ordinary ticket continues the SAVED baseline
            assert (
                queue_service.get_next_queue_number(
                    db_session, daily_queue=restored, queue_tag=restored.queue_tag
                )
                == 41
            )
        finally:
            leftover = (
                db_session.query(DailyQueue).filter(DailyQueue.id == queue_id).first()
            )
            if leftover is not None:
                db_session.query(OnlineQueueEntry).filter(
                    OnlineQueueEntry.queue_id == queue_id
                ).delete(synchronize_session=False)
                db_session.delete(leftover)
                db_session.commit()

    def test_restore_legacy_backup_without_start_number_uses_default(
        self, db_session, tmp_path
    ):
        """R19 P2 compat pin: pre-snapshot backups (no start_number key
        in the JSON) stay restorable — the row comes back at the column
        default (1). The explicitly defined compatible behavior, same
        contract as queue_resource_id (QD-2A)."""
        backup_data = {
            "backup_date": date.today().isoformat(),
            "created_at": datetime.utcnow().isoformat(),
            "queues": [
                {
                    "id": 998,
                    "day": date.today().isoformat(),
                    "specialist_id": 1,
                    "queue_tag": "r19_legacy",
                    "active": True,
                    "opened_at": None,
                    "entries": [],
                }
            ],
        }
        backup_file = tmp_path / "legacy_backup.json"
        backup_file.write_text(json.dumps(backup_data), encoding="utf-8")

        service = MigrationService(db_session)
        try:
            result = service.restore_queue_data(str(backup_file))
            assert result["success"] is True, result

            restored = (
                db_session.query(DailyQueue).filter(DailyQueue.id == 998).first()
            )
            assert restored is not None
            assert restored.start_number == 1
        finally:
            leftover = (
                db_session.query(DailyQueue).filter(DailyQueue.id == 998).first()
            )
            if leftover is not None:
                db_session.delete(leftover)
                db_session.commit()
