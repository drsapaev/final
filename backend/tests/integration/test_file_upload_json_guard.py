from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from app.api.v1.endpoints import file_upload_json


UPLOAD_JSON_PATH = "/api/v1/files/upload-json"


def _payload(content: bytes) -> dict[str, str]:
    return {
        "filename": "note.txt",
        "content": base64.b64encode(content).decode("ascii"),
        "title": "Test note",
    }


def test_patient_cannot_use_legacy_json_upload(
    client: TestClient,
    patient_token: str,
) -> None:
    response = client.post(
        UPLOAD_JSON_PATH,
        headers={"Authorization": f"Bearer {patient_token}"},
        json=_payload(b"hello"),
    )

    assert response.status_code == 403


def test_staff_can_upload_small_json_file(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)

    response = client.post(
        UPLOAD_JSON_PATH,
        headers=auth_headers,
        json=_payload(b"hello"),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["file_size"] == 5
    assert (tmp_path / payload["file_path"]).is_file()


def test_json_upload_rejects_oversized_payload_before_write(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(file_upload_json, "MAX_JSON_UPLOAD_BYTES", 3)
    monkeypatch.setattr(file_upload_json, "MAX_JSON_UPLOAD_BASE64_CHARS", 4)

    response = client.post(
        UPLOAD_JSON_PATH,
        headers=auth_headers,
        json=_payload(b"abcd"),
    )

    assert response.status_code == 413
    assert not (tmp_path / "uploads").exists()
