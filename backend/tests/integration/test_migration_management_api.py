"""
Интеграционные тесты для API управления миграциями
"""
import json
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry


@pytest.mark.integration
@pytest.mark.migration
class TestMigrationManagementAPI:
    """Интеграционные тесты для API управления миграциями"""
    
    def test_check_migration_health_success(self, client, auth_headers):
        """Тест проверки состояния системы миграций"""
        response = client.get("/api/v1/admin/migration/health", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "healthy" in data
        assert "checks" in data
        assert "checked_at" in data
        assert isinstance(data["checks"], dict)
    
    def test_check_migration_health_unauthorized(self, client):
        """Тест проверки состояния без авторизации"""
        response = client.get("/api/v1/admin/migration/health")
        
        assert response.status_code == 401
    
    def test_check_migration_health_wrong_role(self, client, cardio_auth_headers):
        """Тест проверки состояния с неправильной ролью"""
        response = client.get("/api/v1/admin/migration/health", headers=cardio_auth_headers)
        
        assert response.status_code == 403
    
    def test_check_data_integrity_success(self, client, auth_headers):
        """Тест проверки целостности данных"""
        response = client.get("/api/v1/admin/migration/check-integrity", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "passed" in data
        assert "checks" in data
        assert "checked_at" in data
        assert isinstance(data["checks"], dict)
        
        # Проверяем наличие основных проверок
        checks = data["checks"]
        assert "duplicate_numbers" in checks
        assert "orphaned_visits" in checks
        assert "orphaned_patients" in checks
        assert "orphaned_queues" in checks
    
    def test_check_data_integrity_with_data(self, client, auth_headers, test_queue_entry):
        """Тест проверки целостности с существующими данными"""
        response = client.get("/api/v1/admin/migration/check-integrity", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # С корректными данными все проверки должны пройти
        assert data["passed"] is True
        for check_name, check_result in data["checks"].items():
            assert check_result["passed"] is True
    
    def test_get_migration_stats_success(self, client, auth_headers):
        """Тест получения статистики миграций"""
        response = client.get("/api/v1/admin/migration/stats", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "queue_statistics" in data
        assert "entry_statistics" in data
        assert "source_distribution" in data
        assert "queue_tag_distribution" in data
        assert "generated_at" in data
        
        # Проверяем структуру статистики очередей
        queue_stats = data["queue_statistics"]
        assert "total_queues" in queue_stats
        assert "active_queues" in queue_stats
        assert "opened_queues" in queue_stats
        
        # Проверяем структуру статистики записей
        entry_stats = data["entry_statistics"]
        assert "total_entries" in entry_stats
        assert "waiting_entries" in entry_stats
        assert "linked_to_visits" in entry_stats
    
    def test_get_migration_stats_with_data(self, client, auth_headers, test_queue_entry):
        """Тест получения статистики с существующими данными"""
        response = client.get("/api/v1/admin/migration/stats", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Должны быть данные
        assert data["queue_statistics"]["total_queues"] >= 1
        assert data["entry_statistics"]["total_entries"] >= 1
        assert len(data["source_distribution"]) >= 1
    
    def test_migrate_legacy_data_success(self, client, auth_headers):
        """Тест миграции legacy данных"""
        response = client.post("/api/v1/admin/migration/migrate-legacy-data", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "success" in data
        assert "migrated_records" in data
        assert "errors" in data
        assert "integrity_check" in data
        assert isinstance(data["errors"], list)
    
    def test_backup_queue_data_success(self, client, auth_headers):
        """Тест создания резервной копии"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Меняем рабочую директорию для тестов
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            
            try:
                response = client.post("/api/v1/admin/migration/backup-queue-data", headers=auth_headers)
                
                assert response.status_code == 200
                data = response.json()
                
                assert "success" in data
                assert "backup_file" in data
                assert "queues_count" in data
                assert "total_entries" in data
                
            finally:
                os.chdir(original_cwd)
    
    def test_backup_queue_data_specific_date(self, client, auth_headers, test_daily_queue):
        """Тест создания резервной копии за конкретную дату"""
        target_date = test_daily_queue.day.strftime("%Y-%m-%d")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            
            try:
                response = client.post(
                    f"/api/v1/admin/migration/backup-queue-data?target_date={target_date}",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["success"] is True
                assert data["queues_count"] >= 1
                
            finally:
                os.chdir(original_cwd)
    
    def test_backup_queue_data_invalid_date(self, client, auth_headers):
        """Тест создания резервной копии с неправильной датой"""
        response = client.post(
            "/api/v1/admin/migration/backup-queue-data?target_date=invalid-date",
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "формат даты" in data["detail"]
    
    def test_restore_queue_data_success(self, client, auth_headers, db_session):
        """Тест восстановления данных из резервной копии"""
        # Создаем тестовый файл резервной копии
        backup_data = {
            "backup_date": date.today().isoformat(),
            "created_at": datetime.utcnow().isoformat(),
            "queues": [{
                "id": 9999,
                "day": date.today().isoformat(),
                "specialist_id": 1,
                "queue_tag": "test_restore",
                "active": True,
                "opened_at": None,
                "entries": [{
                    "id": 9999,
                    "number": 1,
                    "patient_id": None,
                    "patient_name": "Test Restore Patient",
                    "phone": "+998901111111",
                    "telegram_id": None,
                    "visit_id": None,
                    "source": "test_restore",
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
            response = client.post(
                f"/api/v1/admin/migration/restore-queue-data?backup_file={backup_file}",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert data["restored_queues"] >= 1
            assert data["restored_entries"] >= 1
            
            # Проверяем что данные действительно восстановились
            queue = db_session.query(DailyQueue).filter(DailyQueue.id == 9999).first()
            assert queue is not None
            assert queue.queue_tag == "test_restore"
            
        finally:
            os.unlink(backup_file)
    
    def test_restore_queue_data_file_not_found(self, client, auth_headers):
        """Тест восстановления из несуществующего файла"""
        response = client.post(
            "/api/v1/admin/migration/restore-queue-data?backup_file=nonexistent.json",
            headers=auth_headers
        )
        
        assert response.status_code == 500
        data = response.json()
        assert "Ошибка восстановления" in data["detail"]
    
    def test_cleanup_old_data_success(self, client, auth_headers):
        """Тест очистки старых данных"""
        response = client.post(
            "/api/v1/admin/migration/cleanup-old-data?days_to_keep=30",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "success" in data
        assert "deleted_queues" in data
        assert "deleted_entries" in data
        assert "cutoff_date" in data
    
    def test_cleanup_old_data_with_old_data(self, client, auth_headers, db_session, cardio_user):
        """Тест очистки с существующими старыми данными"""
        # Создаем старую очередь
        old_date = date.today() - timedelta(days=40)
        old_queue = DailyQueue(
            day=old_date,
            specialist_id=cardio_user.id,
            queue_tag="old_test_queue",
            active=False
        )
        db_session.add(old_queue)
        db_session.commit()
        
        response = client.post(
            "/api/v1/admin/migration/cleanup-old-data?days_to_keep=30",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["deleted_queues"] >= 1
    
    def test_cleanup_old_data_invalid_days(self, client, auth_headers):
        """Тест очистки с неправильным количеством дней"""
        response = client.post(
            "/api/v1/admin/migration/cleanup-old-data?days_to_keep=0",
            headers=auth_headers
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_cleanup_old_data_max_days(self, client, auth_headers):
        """Тест очистки с максимальным количеством дней"""
        response = client.post(
            "/api/v1/admin/migration/cleanup-old-data?days_to_keep=365",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_all_endpoints_require_admin_role(self, client, cardio_auth_headers):
        """Тест что все эндпоинты требуют роль администратора"""
        endpoints = [
            "/api/v1/admin/migration/health",
            "/api/v1/admin/migration/check-integrity",
            "/api/v1/admin/migration/stats",
            "/api/v1/admin/migration/migrate-legacy-data",
            "/api/v1/admin/migration/backup-queue-data",
            "/api/v1/admin/migration/cleanup-old-data"
        ]
        
        for endpoint in endpoints:
            if endpoint.endswith("migrate-legacy-data") or endpoint.endswith("backup-queue-data") or endpoint.endswith("cleanup-old-data"):
                response = client.post(endpoint, headers=cardio_auth_headers)
            else:
                response = client.get(endpoint, headers=cardio_auth_headers)
            
            assert response.status_code == 403, f"Endpoint {endpoint} should require admin role"
    
    def test_api_error_handling(self, client, auth_headers):
        """Тест обработки ошибок в API"""
        # Тест с некорректными параметрами
        response = client.post(
            "/api/v1/admin/migration/cleanup-old-data?days_to_keep=invalid",
            headers=auth_headers
        )
        
        assert response.status_code == 422
        
        # Тест восстановления с некорректным файлом
        response = client.post(
            "/api/v1/admin/migration/restore-queue-data?backup_file=",
            headers=auth_headers
        )
        
        assert response.status_code == 422
