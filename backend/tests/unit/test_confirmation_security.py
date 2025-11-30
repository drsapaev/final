"""
Юнит тесты для системы безопасности подтверждения визитов
"""
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from app.models.patient import Patient
from app.models.visit import Visit
from app.services.confirmation_security import (
    ConfirmationSecurityService,
    SecurityCheckResult,
)


@pytest.mark.unit
@pytest.mark.security
class TestConfirmationSecurityService:
    """Тесты для ConfirmationSecurityService"""
    
    def test_validate_confirmation_request_valid_token(self, db_session, test_visit):
        """Тест валидации корректного токена"""
        service = ConfirmationSecurityService(db_session)
        
        result = service.validate_confirmation_request(
            token=test_visit.confirmation_token,
            source_ip="192.168.1.1",
            user_agent="TestAgent/1.0",
            channel="telegram"
        )
        
        assert result.allowed is True
        assert "проверки безопасности" in result.reason
    
    def test_validate_confirmation_request_invalid_token(self, db_session):
        """Тест валидации несуществующего токена"""
        service = ConfirmationSecurityService(db_session)
        
        result = service.validate_confirmation_request(
            token="invalid-token-123",
            source_ip="192.168.1.1",
            user_agent="TestAgent/1.0",
            channel="telegram"
        )
        
        assert result.allowed is False
        assert "Недействительный токен" in result.reason
    
    def test_validate_confirmation_request_expired_token(self, db_session, test_visit):
        """Тест валидации истекшего токена"""
        # Устанавливаем время истечения в прошлом
        test_visit.confirmation_expires_at = datetime.utcnow() - timedelta(hours=1)
        db_session.commit()
        
        service = ConfirmationSecurityService(db_session)
        
        result = service.validate_confirmation_request(
            token=test_visit.confirmation_token,
            source_ip="192.168.1.1",
            user_agent="TestAgent/1.0",
            channel="telegram"
        )
        
        assert result.allowed is False
        assert "Срок действия токена истек" in result.reason
    
    def test_validate_confirmation_request_wrong_status(self, db_session, test_visit):
        """Тест валидации токена с неправильным статусом визита"""
        test_visit.status = "confirmed"
        db_session.commit()
        
        service = ConfirmationSecurityService(db_session)
        
        result = service.validate_confirmation_request(
            token=test_visit.confirmation_token,
            source_ip="192.168.1.1",
            user_agent="TestAgent/1.0",
            channel="telegram"
        )
        
        assert result.allowed is False
        assert "уже имеет статус" in result.reason
    
    def test_validate_confirmation_request_suspicious_user_agent(self, db_session, test_visit):
        """Тест обнаружения подозрительного User-Agent"""
        service = ConfirmationSecurityService(db_session)
        
        result = service.validate_confirmation_request(
            token=test_visit.confirmation_token,
            source_ip="192.168.1.1",
            user_agent="Googlebot/2.1",
            channel="telegram"
        )
        
        assert result.allowed is False
        assert "подозрительный User-Agent" in result.reason
    
    def test_validate_token_generation_request_valid(self, db_session, test_patient):
        """Тест валидации корректного запроса на генерацию токена"""
        service = ConfirmationSecurityService(db_session)
        
        result = service.validate_token_generation_request(
            patient_id=test_patient.id,
            source_ip="192.168.1.1",
            user_id=1
        )
        
        assert result.allowed is True
        assert "разрешена" in result.reason
    
    def test_generate_secure_token(self, db_session):
        """Тест генерации безопасного токена"""
        service = ConfirmationSecurityService(db_session)
        
        token = service.generate_secure_token(visit_id=123)
        
        assert isinstance(token, str)
        assert len(token) > 40  # Должен быть достаточно длинным
        assert "-" in token  # Должен содержать разделитель
    
    def test_generate_secure_token_uniqueness(self, db_session):
        """Тест уникальности генерируемых токенов"""
        service = ConfirmationSecurityService(db_session)
        
        token1 = service.generate_secure_token(visit_id=123)
        token2 = service.generate_secure_token(visit_id=123)
        
        assert token1 != token2
    
    def test_record_confirmation_attempt_success(self, db_session, test_visit):
        """Тест записи успешной попытки подтверждения"""
        service = ConfirmationSecurityService(db_session)
        
        # Не должно вызывать исключений
        service.record_confirmation_attempt(
            visit_id=test_visit.id,
            success=True,
            source_ip="192.168.1.1",
            user_agent="TestAgent/1.0",
            channel="telegram"
        )
    
    def test_record_confirmation_attempt_failure(self, db_session, test_visit):
        """Тест записи неудачной попытки подтверждения"""
        service = ConfirmationSecurityService(db_session)
        
        # Не должно вызывать исключений
        service.record_confirmation_attempt(
            visit_id=test_visit.id,
            success=False,
            source_ip="192.168.1.1",
            user_agent="TestAgent/1.0",
            channel="telegram",
            error_reason="Test error"
        )
    
    def test_cleanup_expired_tokens(self, db_session):
        """Тест очистки истекших токенов"""
        # Создаем визит с истекшим токеном
        expired_visit = Visit(
            patient_id=1,
            status="pending_confirmation",
            confirmation_token="expired-token",
            confirmation_expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        db_session.add(expired_visit)
        db_session.commit()
        
        service = ConfirmationSecurityService(db_session)
        cleaned_count = service.cleanup_expired_tokens()
        
        assert cleaned_count >= 1
        
        # Проверяем что статус изменился
        db_session.refresh(expired_visit)
        assert expired_visit.status == "expired"
        assert expired_visit.confirmation_token is None
    
    def test_get_security_stats(self, db_session):
        """Тест получения статистики безопасности"""
        service = ConfirmationSecurityService(db_session)
        
        stats = service.get_security_stats(hours=24)
        
        assert isinstance(stats, dict)
        assert "period_hours" in stats
        assert "since" in stats
        assert stats["period_hours"] == 24
    
    @patch('app.services.confirmation_security.logger')
    def test_logging_security_events(self, mock_logger, db_session, test_visit):
        """Тест логирования событий безопасности"""
        service = ConfirmationSecurityService(db_session)
        
        service.validate_confirmation_request(
            token="invalid-token",
            source_ip="192.168.1.1",
            user_agent="TestAgent/1.0",
            channel="telegram"
        )
        
        # Проверяем что логирование вызывалось
        assert mock_logger.info.called


@pytest.mark.unit
@pytest.mark.security
class TestSecurityCheckResult:
    """Тесты для SecurityCheckResult"""
    
    def test_security_check_result_creation(self):
        """Тест создания результата проверки безопасности"""
        result = SecurityCheckResult(
            allowed=True,
            reason="Test reason",
            retry_after=60,
            remaining_attempts=3
        )
        
        assert result.allowed is True
        assert result.reason == "Test reason"
        assert result.retry_after == 60
        assert result.remaining_attempts == 3
    
    def test_security_check_result_defaults(self):
        """Тест значений по умолчанию"""
        result = SecurityCheckResult(
            allowed=False,
            reason="Test reason"
        )
        
        assert result.allowed is False
        assert result.reason == "Test reason"
        assert result.retry_after is None
        assert result.remaining_attempts is None
