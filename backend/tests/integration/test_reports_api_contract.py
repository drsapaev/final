from __future__ import annotations

from types import SimpleNamespace


def test_advertised_report_types_have_backend_routes(client, auth_headers, monkeypatch):
    from app.api.v1.endpoints import reports

    class FakeReportingService:
        def generate_queue_report(self, **kwargs):
            return {
                "format": kwargs["format"],
                "data": {"report_type": "queue_report"},
                "filename": "queue.csv",
                "size": 10,
            }

        def generate_doctor_performance_report(self, **kwargs):
            return {
                "format": kwargs["format"],
                "data": {"report_type": "doctor_performance_report"},
                "filename": "doctor.xlsx",
                "size": 20,
            }

    monkeypatch.setattr(
        reports,
        "get_reporting_service",
        lambda db: FakeReportingService(),
    )

    queue_response = client.post(
        "/api/v1/reports/queue",
        headers=auth_headers,
        json={"format": "json"},
    )
    assert queue_response.status_code == 200, queue_response.text
    assert queue_response.json()["report_type"] == "queue_report"

    doctor_response = client.post(
        "/api/v1/reports/doctor-performance",
        headers=auth_headers,
        json={"format": "json"},
    )
    assert doctor_response.status_code == 200, doctor_response.text
    assert doctor_response.json()["report_type"] == "doctor_performance_report"


def test_report_download_matches_files_contract_and_blocks_path_traversal(
    client,
    auth_headers,
    monkeypatch,
    tmp_path,
):
    from app.api.v1.endpoints import reports

    report_file = tmp_path / "daily.csv"
    report_file.write_bytes(b"patient,total\nA,1\n")
    hidden_dir = tmp_path / "hidden"
    hidden_dir.mkdir()
    hidden_file = hidden_dir / "secret.csv"
    hidden_file.write_text("secret", encoding="utf-8")

    monkeypatch.setattr(
        reports,
        "get_reporting_service",
        lambda db: SimpleNamespace(reports_dir=str(tmp_path)),
    )

    response = client.get(
        "/api/v1/reports/download/daily.csv",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.content == b"patient,total\nA,1\n"
    assert "daily.csv" in response.headers["content-disposition"]

    traversal_response = client.get(
        "/api/v1/reports/download/hidden%2Fsecret.csv",
        headers=auth_headers,
    )
    assert traversal_response.status_code == 404
    assert b"secret" not in traversal_response.content


def test_patient_cannot_download_admin_report_files(client, patient_token, monkeypatch, tmp_path):
    from app.api.v1.endpoints import reports

    (tmp_path / "daily.csv").write_text("patient,total\nA,1\n", encoding="utf-8")
    monkeypatch.setattr(
        reports,
        "get_reporting_service",
        lambda db: SimpleNamespace(reports_dir=str(tmp_path)),
    )

    response = client.get(
        "/api/v1/reports/download/daily.csv",
        headers={"Authorization": f"Bearer {patient_token}"},
    )

    assert response.status_code == 403
