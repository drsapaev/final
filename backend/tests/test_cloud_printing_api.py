from __future__ import annotations

import pytest

from app.services.cloud_printing_service import MockPrintProvider


@pytest.mark.integration
def test_cloud_printing_mock_job_persists_across_requests(client, auth_headers):
    MockPrintProvider.reset_mock_state()

    printers_response = client.get("/api/v1/cloud-printing/printers", headers=auth_headers)
    assert printers_response.status_code == 200
    printers = printers_response.json()["printers"]
    mock_printer = next(item for item in printers if item["provider"] == "mock")

    submit_response = client.post(
        f"/api/v1/cloud-printing/test/{mock_printer['provider']}/{mock_printer['id']}",
        headers=auth_headers,
    )
    assert submit_response.status_code == 200
    submit_payload = submit_response.json()
    assert submit_payload["success"] is True
    job_id = submit_payload["job_id"]

    status_response = client.get(
        f"/api/v1/cloud-printing/jobs/{mock_printer['provider']}/{job_id}/status",
        headers=auth_headers,
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "completed"

    cancel_response = client.post(
        f"/api/v1/cloud-printing/jobs/{mock_printer['provider']}/{job_id}/cancel",
        headers=auth_headers,
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["success"] is True

    cancelled_status_response = client.get(
        f"/api/v1/cloud-printing/jobs/{mock_printer['provider']}/{job_id}/status",
        headers=auth_headers,
    )
    assert cancelled_status_response.status_code == 200
    assert cancelled_status_response.json()["status"] == "cancelled"
