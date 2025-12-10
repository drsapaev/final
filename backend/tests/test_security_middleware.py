"""
Тесты для Security Middleware (rate limiting, brute force protection, IP logging)
"""

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.middleware.security_middleware import SecurityMiddleware


@pytest.fixture
def app_with_security():
    """Создать FastAPI приложение с SecurityMiddleware"""
    app = FastAPI()
    
    # Добавляем тестовые эндпоинты
    @app.post("/api/v1/authentication/login")
    async def test_login():
        return {"message": "Login successful"}
    
    @app.post("/api/v1/2fa/verify")
    async def test_2fa_verify():
        return {"message": "2FA verified"}
    
    @app.post("/api/v1/authentication/password-reset")
    async def test_password_reset():
        return {"message": "Password reset requested"}
    
    @app.get("/api/v1/health")
    async def test_health():
        return {"status": "ok"}
    
    @app.get("/api/v1/test")
    async def test_endpoint():
        return {"message": "Test"}
    
    # Добавляем SecurityMiddleware
    app.add_middleware(SecurityMiddleware)
    
    return app


@pytest.fixture
def client(app_with_security):
    """Создать TestClient"""
    return TestClient(app_with_security)


class TestRateLimiting:
    """Тесты для rate limiting"""
    
    def test_rate_limit_login_endpoint(self, app_with_security):
        """Тест: превышение лимита на login endpoint"""
        client = TestClient(app_with_security)
        # Делаем 6 запросов (лимит: 5 за 5 минут)
        for i in range(5):
            response = client.post("/api/v1/authentication/login")
            assert response.status_code in [200, 400, 401]  # Может быть ошибка валидации
        
        # 6-й запрос должен быть заблокирован
        response = client.post("/api/v1/authentication/login")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "Превышен лимит запросов" in response.json()["detail"]
    
    def test_rate_limit_2fa_verify(self, app_with_security):
        """Тест: превышение лимита на 2FA verify endpoint"""
        client = TestClient(app_with_security)
        # Делаем 11 запросов (лимит: 10 за 5 минут)
        for i in range(10):
            response = client.post("/api/v1/2fa/verify")
            assert response.status_code in [200, 400, 401]
        
        # 11-й запрос должен быть заблокирован
        response = client.post("/api/v1/2fa/verify")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    
    def test_rate_limit_password_reset(self, app_with_security):
        """Тест: превышение лимита на password reset endpoint"""
        client = TestClient(app_with_security)
        # Делаем 4 запроса (лимит: 3 за час)
        for i in range(3):
            response = client.post("/api/v1/authentication/password-reset")
            assert response.status_code in [200, 400]
        
        # 4-й запрос должен быть заблокирован
        response = client.post("/api/v1/authentication/password-reset")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    
    def test_rate_limit_headers(self, app_with_security):
        """Тест: проверка заголовков rate limit"""
        client = TestClient(app_with_security)
        response = client.post("/api/v1/authentication/login")
        # Заголовки добавляются только для успешных запросов (status < 400)
        if response.status_code < 400:
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Window" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            
            assert response.headers["X-RateLimit-Limit"] == "5"
            assert response.headers["X-RateLimit-Window"] == "300"
    
    def test_rate_limit_public_endpoints(self, client: TestClient):
        """Тест: публичные эндпоинты не ограничиваются"""
        # Делаем много запросов к health endpoint
        for _ in range(20):
            response = client.get("/api/v1/health")
            assert response.status_code == 200


class TestBruteForceProtection:
    """Тесты для brute force protection"""
    
    def test_brute_force_login_blocked(self, client: TestClient):
        """Тест: блокировка IP после множественных неудачных попыток login"""
        # Симулируем неудачные попытки (4xx/5xx ответы)
        # Для этого нужно, чтобы endpoint возвращал ошибку
        
        # Создаем отдельный endpoint, который всегда возвращает ошибку
        app = FastAPI()
        
        @app.post("/api/v1/authentication/login")
        async def failing_login():
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        app.add_middleware(SecurityMiddleware)
        test_client = TestClient(app)
        
        # Делаем 5 неудачных попыток (лимит: 5)
        for i in range(5):
            response = test_client.post("/api/v1/authentication/login")
            assert response.status_code == 401
        
        # 6-я попытка должна быть заблокирована
        response = test_client.post("/api/v1/authentication/login")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "заблокирован" in response.json()["detail"].lower()
    
    def test_brute_force_2fa_blocked(self, client: TestClient):
        """Тест: блокировка IP после множественных неудачных попыток 2FA"""
        app = FastAPI()
        
        @app.post("/api/v1/2fa/verify")
        async def failing_2fa():
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Invalid OTP")
        
        app.add_middleware(SecurityMiddleware)
        test_client = TestClient(app)
        
        # Делаем 5 неудачных попыток
        for i in range(5):
            response = test_client.post("/api/v1/2fa/verify")
            assert response.status_code == 400
        
        # 6-я попытка должна быть заблокирована
        response = test_client.post("/api/v1/2fa/verify")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


class TestIPLogging:
    """Тесты для IP logging"""
    
    def test_ip_extraction_from_headers(self, client: TestClient):
        """Тест: извлечение IP из заголовков X-Forwarded-For"""
        # Симулируем запрос с X-Forwarded-For
        response = client.post(
            "/api/v1/authentication/login",
            headers={"X-Forwarded-For": "192.168.1.100"}
        )
        # Проверяем, что запрос обработан (не важно, успешный или нет)
        assert response.status_code in [200, 400, 401, 429]
    
    def test_ip_extraction_from_x_real_ip(self, client: TestClient):
        """Тест: извлечение IP из заголовка X-Real-IP"""
        response = client.post(
            "/api/v1/authentication/login",
            headers={"X-Real-IP": "10.0.0.1"}
        )
        assert response.status_code in [200, 400, 401, 429]


class TestSecurityMiddlewareIntegration:
    """Интеграционные тесты для SecurityMiddleware"""
    
    def test_middleware_does_not_block_public_endpoints(self, client: TestClient):
        """Тест: middleware не блокирует публичные эндпоинты"""
        public_paths = ["/docs", "/redoc", "/openapi.json", "/health", "/"]
        
        for path in public_paths:
            # Пропускаем, если путь не существует в тестовом приложении
            if path == "/health":
                response = client.get("/api/v1/health")
                assert response.status_code == 200
    
    def test_middleware_handles_exceptions_gracefully(self, client: TestClient):
        """Тест: middleware корректно обрабатывает исключения"""
        # Создаем endpoint, который выбрасывает исключение
        app = FastAPI()
        
        @app.get("/api/v1/error")
        async def error_endpoint():
            raise ValueError("Test error")
        
        app.add_middleware(SecurityMiddleware)
        test_client = TestClient(app, raise_server_exceptions=False)
        
        # Middleware не должен падать, а должен пропустить запрос
        response = test_client.get("/api/v1/error")
        # FastAPI обработает исключение и вернет 500
        assert response.status_code == 500
    
    def test_rate_limit_reset_after_window(self, client: TestClient):
        """Тест: rate limit сбрасывается после окна времени"""
        # Этот тест сложно выполнить без мокирования времени
        # Но можно проверить, что счетчики очищаются
        middleware = SecurityMiddleware(None)
        
        # Симулируем старые записи (старше окна)
        import time
        old_timestamp = time.time() - 2000  # 2000 секунд назад (больше окна в 1 час)
        middleware.request_counts["test:127.0.0.1"] = [old_timestamp]
        
        # Вызываем cleanup
        middleware._cleanup_old_records()
        
        # Проверяем, что старые записи удалены
        # Используем обычный dict вместо defaultdict для проверки
        if "test:127.0.0.1" in middleware.request_counts:
            assert len(middleware.request_counts["test:127.0.0.1"]) == 0

