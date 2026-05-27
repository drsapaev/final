from __future__ import annotations

from fastapi.testclient import TestClient

from app.services import file_system_service
from app.utils import file_validator
from app.utils.file_validator import FileCategory


def test_canonical_file_upload_rejects_oversized_payload_before_write(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(file_validator, "READ_CHUNK_BYTES", 2)
    monkeypatch.setattr(
        file_validator,
        "SIZE_LIMITS",
        {category: 3 for category in FileCategory},
    )

    response = client.post(
        "/api/v1/files/upload",
        headers=auth_headers,
        data={"file_type": "document"},
        files={"file": ("oversized.txt", b"abcd", "text/plain")},
    )

    assert response.status_code == 400
    assert "exceeds limit" in response.json()["detail"]
    assert not (tmp_path / "uploads").exists()


def test_file_content_replace_rejects_oversized_payload_before_version_write(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(file_validator, "READ_CHUNK_BYTES", 2)
    monkeypatch.setattr(
        file_validator,
        "SIZE_LIMITS",
        {category: 100 for category in FileCategory},
    )
    monkeypatch.setattr(file_system_service, "FILE_READ_CHUNK_BYTES", 2)
    monkeypatch.setattr(file_system_service.file_system_service, "max_file_size", 3)

    create_response = client.post(
        "/api/v1/files/upload",
        headers=auth_headers,
        data={"file_type": "document"},
        files={"file": ("record.txt", b"ok", "text/plain")},
    )
    assert create_response.status_code == 200
    file_id = create_response.json()["id"]

    replace_response = client.put(
        f"/api/v1/files/{file_id}/content",
        headers=auth_headers,
        files={"file": ("record.txt", b"abcd", "text/plain")},
    )

    assert replace_response.status_code == 413
    assert "Файл слишком большой" in replace_response.json()["detail"]
