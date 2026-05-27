from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.v1.endpoints import print_templates


def test_print_template_upload_rejects_oversized_payload_before_write(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(print_templates, "TEMPLATES_DIR", tmp_path)
    monkeypatch.setattr(print_templates, "PRINT_TEMPLATE_READ_CHUNK_BYTES", 2)
    monkeypatch.setattr(print_templates, "MAX_PRINT_TEMPLATE_UPLOAD_BYTES", 3)

    response = client.post(
        "/api/v1/print/templates/templates/upload/ticket",
        headers=auth_headers,
        files={"file": ("ticket.html", b"abcd", "text/html")},
    )

    assert response.status_code == 413
    assert "Print template upload is too large" in response.json()["detail"]
    assert not (tmp_path / "ticket_ru.j2").exists()
