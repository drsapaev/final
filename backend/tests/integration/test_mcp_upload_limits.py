from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import mcp


@pytest.mark.parametrize(
    ("path", "data"),
    [
        ("/api/v1/mcp/imaging/analyze", {"image_type": "xray"}),
        ("/api/v1/mcp/imaging/skin-lesion", {}),
    ],
)
def test_mcp_imaging_rejects_oversized_payload_before_manager_call(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
    path: str,
    data: dict[str, str],
) -> None:
    async def fail_if_called():
        raise AssertionError("MCP manager should not be called for oversized upload")

    monkeypatch.setattr(mcp, "MCP_IMAGE_READ_CHUNK_BYTES", 2)
    monkeypatch.setattr(mcp, "MAX_MCP_IMAGE_UPLOAD_BYTES", 3)
    monkeypatch.setattr(mcp, "get_mcp_manager", fail_if_called)

    response = client.post(
        path,
        headers=auth_headers,
        data=data,
        files={"image": ("oversized.png", b"abcd", "image/png")},
    )

    assert response.status_code == 413
    assert "Image upload is too large" in response.json()["detail"]
