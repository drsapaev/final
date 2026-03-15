from __future__ import annotations

from datetime import date

import pytest


def _doctor_auth_headers(client, test_doctor_user) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": test_doctor_user.username, "password": "doctor123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class _FakeQueueAutoCloseService:
    def __init__(self, _db):
        self.calls: list[tuple[str, object | None]] = []

    def check_and_close_expired_queues(self) -> dict[str, object]:
        self.calls.append(("check_and_close_expired_queues", None))
        return {
            "closed_count": 1,
            "closed_queues": [
                {
                    "queue_id": 7,
                    "specialist_id": 12,
                    "end_time": "17:00",
                    "entries_count": 3,
                }
            ],
            "check_time": "17:01",
            "date": "2026-03-13",
        }

    def get_queues_pending_close(self) -> list[dict[str, object]]:
        self.calls.append(("get_queues_pending_close", None))
        return [
            {
                "queue_id": 9,
                "specialist_id": 4,
                "end_time": "18:00",
                "current_time": "17:15",
                "entries_count": 2,
                "minutes_remaining": 45,
            }
        ]


class _FakeWaitTimeAnalyticsService:
    def __init__(self):
        self.calculate_calls: list[tuple[date, date, str | None, int | None]] = []

    def calculate_accurate_wait_times(
        self,
        start_date: date,
        end_date: date,
        department: str | None = None,
        doctor_id: int | None = None,
    ) -> dict[str, object]:
        self.calculate_calls.append((start_date, end_date, department, doctor_id))
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_entries": 10,
                "analyzed_entries": 8,
            },
            "overall_stats": {
                "count": 8,
                "average_minutes": 14.5,
                "median_minutes": 12.0,
                "min_minutes": 3.0,
                "max_minutes": 28.0,
                "std_deviation": 5.1,
                "percentile_75": 17.0,
                "percentile_90": 25.0,
                "percentile_95": 27.0,
            },
            "department_breakdown": {"lab": {"count": 8, "average_minutes": 14.5}},
            "doctor_breakdown": {"15": {"count": 8, "average_minutes": 14.5}},
            "hourly_breakdown": {"09:00": {"count": 3, "average_minutes": 10.0}},
            "daily_breakdown": {"2026-03-02": {"count": 4, "average_minutes": 13.0}},
            "trends": {"trend": "improving", "change_percent": -8.0},
            "recommendations": ["Перераспределить нагрузку на пиковый час"],
        }


@pytest.mark.integration
def test_queue_auto_close_check_and_close_endpoint_preserves_admin_contract(
    client,
    auth_headers,
    monkeypatch,
):
    from app.api.v1.endpoints import queue_auto_close as queue_auto_close_endpoints

    fake_service = _FakeQueueAutoCloseService(None)
    monkeypatch.setattr(
        queue_auto_close_endpoints,
        "QueueAutoCloseService",
        lambda db: fake_service,
    )

    response = client.post(
        "/api/v1/admin/queue-auto-close/check-and-close",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "Закрыто очередей: 1" in payload["message"]
    assert payload["data"]["closed_count"] == 1
    assert payload["data"]["closed_queues"][0]["queue_id"] == 7
    assert fake_service.calls == [("check_and_close_expired_queues", None)]


@pytest.mark.integration
def test_queue_auto_close_pending_close_endpoint_allows_registrar(
    client,
    registrar_auth_headers,
    monkeypatch,
):
    from app.api.v1.endpoints import queue_auto_close as queue_auto_close_endpoints

    fake_service = _FakeQueueAutoCloseService(None)
    monkeypatch.setattr(
        queue_auto_close_endpoints,
        "QueueAutoCloseService",
        lambda db: fake_service,
    )

    response = client.get(
        "/api/v1/admin/queue-auto-close/pending-close",
        headers=registrar_auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == [
        {
            "queue_id": 9,
            "specialist_id": 4,
            "end_time": "18:00",
            "current_time": "17:15",
            "entries_count": 2,
            "minutes_remaining": 45,
        }
    ]
    assert fake_service.calls == [("get_queues_pending_close", None)]


@pytest.mark.integration
def test_wait_time_analytics_endpoint_preserves_query_contract(
    client,
    auth_headers,
    monkeypatch,
):
    from app.api.v1.endpoints import wait_time_analytics as wait_time_analytics_endpoints

    fake_service = _FakeWaitTimeAnalyticsService()
    monkeypatch.setattr(
        wait_time_analytics_endpoints,
        "get_wait_time_analytics_service",
        lambda _db: fake_service,
    )

    response = client.get(
        "/api/v1/analytics/wait-time/wait-time-analytics",
        params={
            "start_date": "2026-03-01",
            "end_date": "2026-03-07",
            "department": "lab",
            "doctor_id": 15,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["period"]["start_date"] == "2026-03-01"
    assert payload["overall_stats"]["average_minutes"] == 14.5
    assert payload["trends"]["trend"] == "improving"
    assert fake_service.calculate_calls == [
        (date(2026, 3, 1), date(2026, 3, 7), "lab", 15)
    ]


@pytest.mark.integration
def test_wait_time_summary_endpoint_allows_doctor_and_matches_frontend_route(
    client,
    test_doctor_user,
    monkeypatch,
):
    from app.api.v1.endpoints import wait_time_analytics as wait_time_analytics_endpoints

    fake_service = _FakeWaitTimeAnalyticsService()
    monkeypatch.setattr(
        wait_time_analytics_endpoints,
        "get_wait_time_analytics_service",
        lambda _db: fake_service,
    )

    response = client.get(
        "/api/v1/analytics/wait-time/wait-time-summary",
        params={"days": 7, "department": "lab"},
        headers=_doctor_auth_headers(client, test_doctor_user),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["period_days"] == 7
    assert payload["department"] == "lab"
    assert payload["total_analyzed_entries"] == 8
    assert payload["average_wait_time_minutes"] == 14.5
    assert payload["top_recommendations"] == ["Перераспределить нагрузку на пиковый час"]
