from app.api.v1.endpoints import webhooks


class _FakeWebhookService:
    def get_system_webhook_stats(self):
        return {
            "total_webhooks": 7,
            "active_webhooks": 5,
            "inactive_webhooks": 2,
            "recent_24h": {
                "total_calls": 11,
                "successful_calls": 9,
                "failed_calls": 2,
                "success_rate": 81.82,
            },
            "pending_retries": 1,
            "unprocessed_events": 3,
        }


def test_system_stats_route_dispatches_before_webhook_id_stats(
    client, auth_headers, monkeypatch
):
    monkeypatch.setattr(
        webhooks,
        "get_webhook_service",
        lambda db: _FakeWebhookService(),
    )

    response = client.get("/api/v1/webhooks/system/stats", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["total_webhooks"] == 7
    assert response.json()["recent_24h"]["successful_calls"] == 9


def test_system_stats_route_keeps_admin_manager_only_permission(
    client, registrar_auth_headers, monkeypatch
):
    def fail_if_called(db):
        raise AssertionError("system stats service should not run for Registrar")

    monkeypatch.setattr(webhooks, "get_webhook_service", fail_if_called)

    response = client.get(
        "/api/v1/webhooks/system/stats",
        headers=registrar_auth_headers,
    )

    assert response.status_code == 403
