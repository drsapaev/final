import time

import pytest
import requests


class TestAPIIntegration:
    """Базовые интеграционные тесты API"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = "http://127.0.0.1:8000"
        self.timeout = 30
        
    def test_health_endpoint(self):
        """Тест health endpoint"""
        response = requests.get(f"{self.base_url}/api/v1/health", timeout=self.timeout)
        assert response.status_code == 200
        assert "status" in response.json()
        
    def test_status_endpoint(self):
        """Тест status endpoint"""
        response = requests.get(f"{self.base_url}/api/v1/status", timeout=self.timeout)
        assert response.status_code == 200
        assert "status" in response.json()
        
    def test_api_responsiveness(self):
        """Тест отзывчивости API"""
        start_time = time.time()
        response = requests.get(f"{self.base_url}/api/v1/health", timeout=self.timeout)
        end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 5.0  # Ответ должен быть быстрым
