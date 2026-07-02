from __future__ import annotations


class _FakeMCPClient:
    async def health_check(self) -> dict[str, str]:
        return {"overall": "healthy"}

    async def get_server_capabilities(self, server: str | None = None) -> dict[str, object]:
        return {"server": server, "capabilities": ["status"]}


class _FakeMCPManager:
    CIRCUIT_BREAKER_THRESHOLD = 5
    CIRCUIT_BREAKER_COOLDOWN = 30

    def __init__(self) -> None:
        self.client = _FakeMCPClient()

    def is_healthy(self) -> bool:
        return True

    def get_metrics(self) -> dict[str, int]:
        return {"requests": 1}

    def get_server_metrics(self, server: str) -> dict[str, object]:
        return {"server": server, "requests": 1}

    def get_circuit_breaker_status(self) -> dict[str, str]:
        return {"complaint": "closed"}

    async def get_capabilities(self) -> dict[str, list[str]]:
        return {"servers": ["complaint"]}


async def _fake_get_mcp_manager() -> _FakeMCPManager:
    return _FakeMCPManager()


def test_mcp_management_status_allows_admin(client, auth_headers, monkeypatch):
    from app.api.v1.endpoints import mcp

    monkeypatch.setattr(mcp, "get_mcp_manager", _fake_get_mcp_manager)

    response = client.get("/api/v1/mcp/status", headers=auth_headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["healthy"] is True
    assert payload["metrics"] == {"requests": 1}
    assert payload["capabilities"] == {"servers": ["complaint"]}


def test_patient_cannot_read_mcp_management_telemetry(client, patient_token):
    patient_headers = {"Authorization": f"Bearer {patient_token}"}

    for path in (
        "/api/v1/mcp/status",
        "/api/v1/mcp/health",
        "/api/v1/mcp/metrics",
        "/api/v1/mcp/circuit-breaker",
        "/api/v1/mcp/capabilities",
    ):
        response = client.get(path, headers=patient_headers)

        assert response.status_code == 403, path
