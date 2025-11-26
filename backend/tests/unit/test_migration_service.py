"""
Юнит тесты для сервиса миграций
"""
import pytest
import json
import tempfile
import os
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from app.services.migration_service import MigrationService
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.visit import Visit


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
        service = MigrationService(db_session)
        
        with patch('os.makedirs'), patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            result = service.backup_queue_data(date.today())
            
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
                    "phone": "+998901234567",
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
