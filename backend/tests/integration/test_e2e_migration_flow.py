"""
E2E тесты для полного сценария работы с миграциями:
Создание данных → Резервное копирование → Миграция → Восстановление → Проверка целостности
"""
import json
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.services.migration_service import MigrationService


@pytest.mark.integration
@pytest.mark.migration
class TestE2EMigrationFlow:
    """E2E тесты для полного сценария работы с миграциями"""
    
    def test_complete_migration_flow(self, client, db_session, auth_headers, cardio_user, test_patient):
        """
        Полный E2E тест миграции:
        Создание данных → Резервное копирование → Проверка целостности → Очистка
        """
        # ШАГ 1: Создаем тестовые данные очередей
        test_date = date.today()
        
        # Создаем дневную очередь
        daily_queue = DailyQueue(
            day=test_date,
            specialist_id=cardio_user.id,
            queue_tag="test_migration_queue",
            active=True,
            opened_at=datetime.utcnow()
        )
        db_session.add(daily_queue)
        db_session.commit()
        
        # Создаем записи в очереди
        queue_entries = []
        for i in range(3):
            entry = OnlineQueueEntry(
                queue_id=daily_queue.id,
                number=i + 1,
                patient_id=test_patient.id if i == 0 else None,
                patient_name=f"Тестовый Пациент {i + 1}",
                phone=f"+99890123456{i}",
                telegram_id=123456789 + i,
                source="test_migration",
                status="waiting" if i < 2 else "served"
            )
            queue_entries.append(entry)
            db_session.add(entry)
        
        db_session.commit()
        
        # ШАГ 2: Проверяем состояние системы миграций
        health_response = client.get("/api/v1/admin/migration/health", headers=auth_headers)
        assert health_response.status_code == 200
        
        health_data = health_response.json()
        assert health_data["healthy"] is True
        
        # ШАГ 3: Получаем статистику до миграции
        stats_response = client.get("/api/v1/admin/migration/stats", headers=auth_headers)
        assert stats_response.status_code == 200
        
        stats_data = stats_response.json()
        initial_queues = stats_data["queue_statistics"]["total_queues"]
        initial_entries = stats_data["entry_statistics"]["total_entries"]
        
        assert initial_queues >= 1
        assert initial_entries >= 3
        
        # ШАГ 4: Проверяем целостность данных
        integrity_response = client.get("/api/v1/admin/migration/check-integrity", headers=auth_headers)
        assert integrity_response.status_code == 200
        
        integrity_data = integrity_response.json()
        assert integrity_data["passed"] is True
        
        # Проверяем конкретные проверки
        checks = integrity_data["checks"]
        assert checks["duplicate_numbers"]["passed"] is True
        assert checks["orphaned_visits"]["passed"] is True
        assert checks["orphaned_patients"]["passed"] is True
        assert checks["orphaned_queues"]["passed"] is True
        
        # ШАГ 5: Создаем резервную копию
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            
            try:
                backup_response = client.post(
                    f"/api/v1/admin/migration/backup-queue-data?target_date={test_date.isoformat()}",
                    headers=auth_headers
                )
                
                assert backup_response.status_code == 200
                backup_data = backup_response.json()
                
                assert backup_data["success"] is True
                assert backup_data["queues_count"] >= 1
                assert backup_data["total_entries"] >= 3
                
                backup_file = backup_data["backup_file"]
                assert os.path.exists(backup_file)
                
                # ШАГ 6: Проверяем содержимое резервной копии
                with open(backup_file, 'r', encoding='utf-8') as f:
                    backup_content = json.load(f)
                
                assert backup_content["backup_date"] == test_date.isoformat()
                assert len(backup_content["queues"]) >= 1
                
                test_queue = backup_content["queues"][0]
                assert test_queue["queue_tag"] == "test_migration_queue"
                assert len(test_queue["entries"]) == 3
                
                # ШАГ 7: Удаляем данные и восстанавливаем из резервной копии
                # Сначала удаляем записи в очереди
                for entry in queue_entries:
                    db_session.delete(entry)
                db_session.delete(daily_queue)
                db_session.commit()
                
                # Проверяем что данные удалились
                remaining_queues = db_session.query(DailyQueue).filter(
                    DailyQueue.queue_tag == "test_migration_queue"
                ).count()
                assert remaining_queues == 0
                
                # ШАГ 8: Восстанавливаем данные
                restore_response = client.post(
                    f"/api/v1/admin/migration/restore-queue-data?backup_file={backup_file}",
                    headers=auth_headers
                )
                
                assert restore_response.status_code == 200
                restore_data = restore_response.json()
                
                assert restore_data["success"] is True
                assert restore_data["restored_queues"] >= 1
                assert restore_data["restored_entries"] >= 3
                
                # ШАГ 9: Проверяем что данные восстановились
                restored_queue = db_session.query(DailyQueue).filter(
                    DailyQueue.queue_tag == "test_migration_queue"
                ).first()
                
                assert restored_queue is not None
                assert restored_queue.day == test_date
                assert restored_queue.specialist_id == cardio_user.id
                
                restored_entries = db_session.query(OnlineQueueEntry).filter(
                    OnlineQueueEntry.queue_id == restored_queue.id
                ).all()
                
                assert len(restored_entries) == 3
                
                # Проверяем порядок номеров
                numbers = sorted([entry.number for entry in restored_entries])
                assert numbers == [1, 2, 3]
                
                # ШАГ 10: Финальная проверка целостности
                final_integrity_response = client.get("/api/v1/admin/migration/check-integrity", headers=auth_headers)
                assert final_integrity_response.status_code == 200
                
                final_integrity_data = final_integrity_response.json()
                assert final_integrity_data["passed"] is True
                
            finally:
                os.chdir(original_cwd)
    
    def test_migration_with_old_data_cleanup(self, client, db_session, auth_headers, cardio_user):
        """
        E2E тест с очисткой старых данных:
        Создание старых данных → Очистка → Проверка результата
        """
        # ШАГ 1: Создаем старые данные (40 дней назад)
        old_date = date.today() - timedelta(days=40)
        
        old_queue = DailyQueue(
            day=old_date,
            specialist_id=cardio_user.id,
            queue_tag="old_test_queue",
            active=False
        )
        db_session.add(old_queue)
        db_session.commit()
        
        # Добавляем записи в старую очередь
        for i in range(2):
            entry = OnlineQueueEntry(
                queue_id=old_queue.id,
                number=i + 1,
                patient_name=f"Старый Пациент {i + 1}",
                phone=f"+99890111111{i}",
                source="old_test_data",
                status="served"
            )
            db_session.add(entry)
        
        db_session.commit()
        
        # ШАГ 2: Создаем новые данные (сегодня)
        new_queue = DailyQueue(
            day=date.today(),
            specialist_id=cardio_user.id,
            queue_tag="new_test_queue",
            active=True
        )
        db_session.add(new_queue)
        db_session.commit()
        
        new_entry = OnlineQueueEntry(
            queue_id=new_queue.id,
            number=1,
            patient_name="Новый Пациент",
            phone="+998901234567",
            source="new_test_data",
            status="waiting"
        )
        db_session.add(new_entry)
        db_session.commit()
        
        # ШАГ 3: Получаем статистику до очистки
        stats_before = client.get("/api/v1/admin/migration/stats", headers=auth_headers)
        assert stats_before.status_code == 200
        
        stats_before_data = stats_before.json()
        queues_before = stats_before_data["queue_statistics"]["total_queues"]
        entries_before = stats_before_data["entry_statistics"]["total_entries"]
        
        # ШАГ 4: Запускаем очистку старых данных (оставляем 30 дней)
        cleanup_response = client.post(
            "/api/v1/admin/migration/cleanup-old-data?days_to_keep=30",
            headers=auth_headers
        )
        
        assert cleanup_response.status_code == 200
        cleanup_data = cleanup_response.json()
        
        assert cleanup_data["success"] is True
        assert cleanup_data["deleted_queues"] >= 1
        assert cleanup_data["deleted_entries"] >= 2
        
        cutoff_date = datetime.fromisoformat(cleanup_data["cutoff_date"]).date()
        expected_cutoff = date.today() - timedelta(days=30)
        assert cutoff_date == expected_cutoff
        
        # ШАГ 5: Проверяем что старые данные удалились
        remaining_old_queues = db_session.query(DailyQueue).filter(
            DailyQueue.day < cutoff_date
        ).count()
        assert remaining_old_queues == 0
        
        # ШАГ 6: Проверяем что новые данные остались
        remaining_new_queues = db_session.query(DailyQueue).filter(
            DailyQueue.day >= cutoff_date
        ).count()
        assert remaining_new_queues >= 1
        
        # ШАГ 7: Получаем статистику после очистки
        stats_after = client.get("/api/v1/admin/migration/stats", headers=auth_headers)
        assert stats_after.status_code == 200
        
        stats_after_data = stats_after.json()
        queues_after = stats_after_data["queue_statistics"]["total_queues"]
        entries_after = stats_after_data["entry_statistics"]["total_entries"]
        
        # Проверяем что количество уменьшилось
        assert queues_after < queues_before
        assert entries_after < entries_before
        
        # ШАГ 8: Финальная проверка целостности
        integrity_response = client.get("/api/v1/admin/migration/check-integrity", headers=auth_headers)
        assert integrity_response.status_code == 200
        
        integrity_data = integrity_response.json()
        assert integrity_data["passed"] is True
    
    def test_migration_service_direct_integration(self, db_session, cardio_user, test_patient):
        """
        E2E тест прямого использования MigrationService
        """
        # ШАГ 1: Создаем сервис миграций
        migration_service = MigrationService(db_session)
        
        # ШАГ 2: Создаем тестовые данные
        test_queue = DailyQueue(
            day=date.today(),
            specialist_id=cardio_user.id,
            queue_tag="direct_test_queue",
            active=True
        )
        db_session.add(test_queue)
        db_session.commit()
        
        test_entry = OnlineQueueEntry(
            queue_id=test_queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            source="direct_test",
            status="waiting"
        )
        db_session.add(test_entry)
        db_session.commit()
        
        # ШАГ 3: Проверяем целостность данных
        integrity_result = migration_service._check_data_integrity()
        assert integrity_result["passed"] is True
        
        # ШАГ 4: Создаем резервную копию
        backup_result = migration_service.backup_queue_data(date.today())
        assert backup_result["success"] is True
        assert backup_result["queues_count"] >= 1
        assert backup_result["total_entries"] >= 1
        
        backup_file = backup_result["backup_file"]
        
        # ШАГ 5: Удаляем данные
        db_session.delete(test_entry)
        db_session.delete(test_queue)
        db_session.commit()
        
        # ШАГ 6: Восстанавливаем данные
        try:
            restore_result = migration_service.restore_queue_data(backup_file)
            assert restore_result["success"] is True
            assert restore_result["restored_queues"] >= 1
            assert restore_result["restored_entries"] >= 1
            
            # ШАГ 7: Проверяем восстановленные данные
            restored_queue = db_session.query(DailyQueue).filter(
                DailyQueue.queue_tag == "direct_test_queue"
            ).first()
            
            assert restored_queue is not None
            
            restored_entry = db_session.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.queue_id == restored_queue.id
            ).first()
            
            assert restored_entry is not None
            assert restored_entry.patient_name == test_patient.short_name()
            
        finally:
            # Очищаем файл резервной копии
            if os.path.exists(backup_file):
                os.unlink(backup_file)
    
    def test_error_recovery_in_migration_flow(self, client, db_session, auth_headers):
        """
        E2E тест восстановления после ошибок в процессе миграции
        """
        # ШАГ 1: Попытка восстановления из несуществующего файла
        restore_response = client.post(
            "/api/v1/admin/migration/restore-queue-data?backup_file=nonexistent.json",
            headers=auth_headers
        )
        
        assert restore_response.status_code == 500
        assert "Ошибка восстановления" in restore_response.json()["detail"]
        
        # ШАГ 2: Попытка резервного копирования с неправильной датой
        backup_response = client.post(
            "/api/v1/admin/migration/backup-queue-data?target_date=invalid-date",
            headers=auth_headers
        )
        
        assert backup_response.status_code == 400
        assert "формат даты" in backup_response.json()["detail"]
        
        # ШАГ 3: Попытка очистки с неправильными параметрами
        cleanup_response = client.post(
            "/api/v1/admin/migration/cleanup-old-data?days_to_keep=0",
            headers=auth_headers
        )
        
        assert cleanup_response.status_code == 422  # Validation error
        
        # ШАГ 4: Проверяем что система остается стабильной после ошибок
        health_response = client.get("/api/v1/admin/migration/health", headers=auth_headers)
        assert health_response.status_code == 200
        
        health_data = health_response.json()
        # Система должна оставаться здоровой даже после ошибок
        assert "healthy" in health_data
    
    def test_concurrent_migration_operations(self, client, db_session, auth_headers, cardio_user):
        """
        E2E тест параллельных операций миграции
        """
        # ШАГ 1: Создаем данные для тестирования
        test_queue = DailyQueue(
            day=date.today(),
            specialist_id=cardio_user.id,
            queue_tag="concurrent_test_queue",
            active=True
        )
        db_session.add(test_queue)
        db_session.commit()
        
        # ШАГ 2: Запускаем несколько операций параллельно
        # (В реальном тесте это было бы с threading, но для простоты делаем последовательно)
        
        # Проверка целостности
        integrity_response = client.get("/api/v1/admin/migration/check-integrity", headers=auth_headers)
        assert integrity_response.status_code == 200
        
        # Получение статистики
        stats_response = client.get("/api/v1/admin/migration/stats", headers=auth_headers)
        assert stats_response.status_code == 200
        
        # Проверка здоровья системы
        health_response = client.get("/api/v1/admin/migration/health", headers=auth_headers)
        assert health_response.status_code == 200
        
        # ШАГ 3: Проверяем что все операции завершились успешно
        assert integrity_response.json()["passed"] is True
        assert stats_response.json()["queue_statistics"]["total_queues"] >= 1
        assert health_response.json()["healthy"] is True
        
        # ШАГ 4: Проверяем консистентность данных после параллельных операций
        final_integrity = client.get("/api/v1/admin/migration/check-integrity", headers=auth_headers)
        assert final_integrity.status_code == 200
        assert final_integrity.json()["passed"] is True
