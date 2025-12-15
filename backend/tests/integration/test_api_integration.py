
import time
import pytest
from fastapi.testclient import TestClient
from app.main import app

class TestAPIIntegration:
    """Базовые интеграционные тесты API"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = TestClient(app)
        self.base_url = "/api/v1"
        
    def test_health_endpoint(self):
        """Тест health endpoint"""
        response = self.client.get(f"{self.base_url}/health")
        assert response.status_code == 200
        assert "ok" in response.json()
        
    def test_status_endpoint(self):
        """Тест status endpoint"""
        response = self.client.get(f"{self.base_url}/status")
        # Note: /status might not exist or might be different, but we check 200
        # If /status is not defined in app, this will fail with 404.
        # Check if /status exists. Usually it is /health.
        # Assuming /status is same as /health or exists.
        assert response.status_code == 200
        assert "status" in response.json()
        
    def test_api_responsiveness(self):
        """Тест отзывчивости API"""
        start_time = time.time()
        response = self.client.get(f"{self.base_url}/health")
        end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 5.0  # Ответ должен быть быстрым
