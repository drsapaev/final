"""Simple integration checks for a running API server in CI/CD."""

import pytest
import requests

BASE_URL = "http://127.0.0.1:8000"


def _ensure_running_server() -> None:
    try:
        response = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
    except requests.RequestException as exc:
        pytest.fail(f"Integration server is not running at {BASE_URL}: {exc}")
    assert response.status_code == 200, (
        "Integration server responded but health endpoint is not OK: "
        f"status={response.status_code}"
    )


def test_health_endpoint() -> None:
    _ensure_running_server()
    response = requests.get(f"{BASE_URL}/api/v1/health", timeout=30)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "ok" in data


def test_status_endpoint() -> None:
    _ensure_running_server()
    response = requests.get(f"{BASE_URL}/api/v1/status", timeout=30)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "status" in data


def test_openapi_docs() -> None:
    _ensure_running_server()
    response = requests.get(f"{BASE_URL}/docs", timeout=30)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

