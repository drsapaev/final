from __future__ import annotations

from datetime import date

from app.models.online_queue import DailyQueue, OnlineQueueEntry


def test_response_contains_trace_and_request_ids(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers.get("x-trace-id")
    assert response.headers.get("x-request-id")


def test_prometheus_metrics_endpoint_available(client):
    response = client.get("/api/v1/observability/metrics")
    assert response.status_code == 200
    assert "clinic_http_requests_total" in response.text
    assert "clinic_http_request_latency_p95_ms" in response.text
    assert "clinic_queue_lag" in response.text


def test_queue_lag_is_reflected_in_metrics(client, db_session, test_doctor, test_patient):
    daily_queue = DailyQueue(
        day=date.today(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    db_session.flush()

    waiting_entry = OnlineQueueEntry(
        queue_id=daily_queue.id,
        number=1,
        patient_id=test_patient.id,
        source="online",
        status="waiting",
    )
    called_entry = OnlineQueueEntry(
        queue_id=daily_queue.id,
        number=2,
        patient_id=test_patient.id,
        source="online",
        status="called",
    )
    db_session.add(waiting_entry)
    db_session.add(called_entry)
    db_session.commit()

    response = client.get("/api/v1/observability/metrics")
    assert response.status_code == 200
    assert "clinic_queue_lag 2" in response.text
