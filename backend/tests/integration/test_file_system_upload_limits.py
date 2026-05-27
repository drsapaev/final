from __future__ import annotations

from fastapi.testclient import TestClient

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
