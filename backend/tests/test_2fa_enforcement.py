"""
Тесты принудительного 2FA для критичных ролей (Admin, Cashier).

Проверяет:
- Admin/Cashier не могут войти без настройки 2FA
- Admin/Cashier могут войти с правильным OTP после настройки 2FA
- Admin/Cashier не могут войти с неправильным OTP
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.two_factor_auth import TwoFactorAuth, TwoFactorBackupCode
from app.models.user import User
from app.services.two_factor_service import get_two_factor_service


@pytest.fixture
def admin_user_without_2fa(db_session: Session) -> User:
    """Создает тестового админа БЕЗ настроенной 2FA"""
    # Проверяем, не существует ли уже пользователь
    existing = db_session.query(User).filter(User.username == "test_admin_2fa").first()
    if existing:
        # Удаляем связанные записи 2FA перед удалением пользователя
        from app.models.two_factor_auth import TwoFactorAuth
        two_fa = db_session.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == existing.id).first()
        if two_fa:
            db_session.delete(two_fa)
        db_session.delete(existing)
        db_session.commit()
    
    user = User(
        username="test_admin_2fa",
        email="admin2fa@test.com",
        full_name="Test Admin 2FA",
        hashed_password=get_password_hash("admin123"),
        role="Admin",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def cashier_user_without_2fa(db_session: Session) -> User:
    """Создает тестового кассира БЕЗ настроенной 2FA"""
    # Проверяем, не существует ли уже пользователь
    existing = db_session.query(User).filter(User.username == "test_cashier_2fa").first()
    if existing:
        db_session.delete(existing)
        db_session.commit()
    
    user = User(
        username="test_cashier_2fa",
        email="cashier2fa@test.com",
        full_name="Test Cashier 2FA",
        hashed_password=get_password_hash("cashier123"),
        role="Cashier",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user_with_2fa(db_session: Session, admin_user_without_2fa: User) -> tuple[User, str]:
    """Создает тестового админа С настроенной 2FA и возвращает secret"""
    service = get_two_factor_service()
    
    # Генерируем secret
    secret = service.generate_totp_secret()
    
    # Создаем объект 2FA напрямую
    two_factor_auth = TwoFactorAuth(
        user_id=admin_user_without_2fa.id,
        totp_secret=secret,
        totp_enabled=True,
        totp_verified=True,
        recovery_enabled=False,
    )
    db_session.add(two_factor_auth)
    db_session.flush()  # Получаем ID для backup кодов
    
    # Создаем backup коды
    backup_codes = service.generate_backup_codes()
    for code in backup_codes:
        backup_code = TwoFactorBackupCode(
            two_factor_auth_id=two_factor_auth.id,
            code=code,
            used=False,
        )
        db_session.add(backup_code)
    
    db_session.commit()
    db_session.refresh(admin_user_without_2fa)
    
    return admin_user_without_2fa, secret


@pytest.fixture
def cashier_user_with_2fa(db_session: Session, cashier_user_without_2fa: User) -> tuple[User, str]:
    """Создает тестового кассира С настроенной 2FA и возвращает secret"""
    service = get_two_factor_service()
    
    # Генерируем secret
    secret = service.generate_totp_secret()
    
    # Создаем объект 2FA напрямую
    two_factor_auth = TwoFactorAuth(
        user_id=cashier_user_without_2fa.id,
        totp_secret=secret,
        totp_enabled=True,
        totp_verified=True,
        recovery_enabled=False,
    )
    db_session.add(two_factor_auth)
    db_session.flush()  # Получаем ID для backup кодов
    
    # Создаем backup коды
    backup_codes = service.generate_backup_codes()
    for code in backup_codes:
        backup_code = TwoFactorBackupCode(
            two_factor_auth_id=two_factor_auth.id,
            code=code,
            used=False,
        )
        db_session.add(backup_code)
    
    db_session.commit()
    db_session.refresh(cashier_user_without_2fa)
    
    return cashier_user_without_2fa, secret


class Test2FAEnforcement:
    """Тесты принудительного 2FA для критичных ролей"""
    
    def test_admin_cannot_login_without_2fa(
        self, client: TestClient, admin_user_without_2fa: User
    ):
        """Admin НЕ может войти без настройки 2FA"""
        response = client.post(
            "/api/v1/authentication/login",
            json={
                "username": admin_user_without_2fa.username,
                "password": "admin123",
            },
        )
        
        # Эндпоинт возвращает 401, когда success=False
        assert response.status_code == 401, f"Expected 401, got {response.status_code}. Response: {response.text}"
        data = response.json()
        assert "detail" in data, "Response should include detail field"
        detail = data["detail"]
        assert "2fa" in detail.lower() or "двухфакторной" in detail.lower(), \
            f"Message should mention 2FA setup requirement. Detail: {detail}"
    
    def test_cashier_cannot_login_without_2fa(
        self, client: TestClient, cashier_user_without_2fa: User
    ):
        """Cashier НЕ может войти без настройки 2FA"""
        response = client.post(
            "/api/v1/authentication/login",
            json={
                "username": cashier_user_without_2fa.username,
                "password": "cashier123",
            },
        )
        
        # Эндпоинт возвращает 401, когда success=False
        assert response.status_code == 401, f"Expected 401, got {response.status_code}. Response: {response.text}"
        data = response.json()
        assert "detail" in data, "Response should include detail field"
        detail = data["detail"]
        assert "2fa" in detail.lower() or "двухфакторной" in detail.lower(), \
            f"Message should mention 2FA setup requirement. Detail: {detail}"
    
    def test_admin_can_login_with_correct_otp(
        self, client: TestClient, admin_user_with_2fa: tuple[User, str]
    ):
        """Admin может войти с правильным OTP после настройки 2FA"""
        admin_user, secret = admin_user_with_2fa
        service = get_two_factor_service()
        
        # Генерируем правильный OTP код
        correct_otp = service.generate_totp_code(secret)
        
        # Шаг 1: Логин должен вернуть pending_2fa_token
        login_response = client.post(
            "/api/v1/authentication/login",
            json={
                "username": admin_user.username,
                "password": "admin123",
            },
        )
        assert login_response.status_code == 200
        login_data = login_response.json()
        # LoginResponse не содержит success, но содержит requires_2fa и pending_2fa_token
        assert login_data.get("requires_2fa") is True, "2FA should be required"
        assert "pending_2fa_token" in login_data and login_data["pending_2fa_token"] is not None, \
            "pending_2fa_token should be returned"
        pending_token = login_data["pending_2fa_token"]
        
        # Шаг 2: Верификация OTP должна вернуть access_token
        # pending_2fa_token передается в теле запроса, не в заголовке
        verify_response = client.post(
            "/api/v1/2fa/verify",
            json={
                "totp_code": correct_otp,
                "pending_2fa_token": pending_token,
            },
        )
        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        assert verify_data["success"] is True, "2FA verification should succeed"
        assert "access_token" in verify_data, "access_token should be returned after 2FA verification"
    
    def test_admin_cannot_login_with_incorrect_otp(
        self, client: TestClient, admin_user_with_2fa: tuple[User, str]
    ):
        """Admin НЕ может войти с неправильным OTP"""
        admin_user, secret = admin_user_with_2fa
        
        # Шаг 1: Логин должен вернуть pending_2fa_token
        login_response = client.post(
            "/api/v1/authentication/login",
            json={
                "username": admin_user.username,
                "password": "admin123",
            },
        )
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert login_data["requires_2fa"] is True
        pending_token = login_data["pending_2fa_token"]
        
        # Шаг 2: Верификация с неправильным OTP должна провалиться
        verify_response = client.post(
            "/api/v1/2fa/verify",
            json={
                "totp_code": "000000",  # Неправильный код
                "pending_2fa_token": pending_token,
            },
        )
        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        assert verify_data["success"] is False, "2FA verification should fail with incorrect OTP"
        assert "access_token" not in verify_data or verify_data.get("access_token") is None, \
            "No access_token should be returned for incorrect OTP"
    
    def test_cashier_can_login_with_correct_otp(
        self, client: TestClient, cashier_user_with_2fa: tuple[User, str]
    ):
        """Cashier может войти с правильным OTP после настройки 2FA"""
        cashier_user, secret = cashier_user_with_2fa
        service = get_two_factor_service()
        
        # Генерируем правильный OTP код
        correct_otp = service.generate_totp_code(secret)
        
        # Шаг 1: Логин должен вернуть pending_2fa_token
        login_response = client.post(
            "/api/v1/authentication/login",
            json={
                "username": cashier_user.username,
                "password": "cashier123",
            },
        )
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert login_data["requires_2fa"] is True
        pending_token = login_data["pending_2fa_token"]
        
        # Шаг 2: Верификация OTP должна вернуть access_token
        verify_response = client.post(
            "/api/v1/2fa/verify",
            json={
                "totp_code": correct_otp,
                "pending_2fa_token": pending_token,
            },
            headers={"Authorization": f"Bearer {pending_token}"},
        )
        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        assert verify_data["success"] is True
        assert "access_token" in verify_data

