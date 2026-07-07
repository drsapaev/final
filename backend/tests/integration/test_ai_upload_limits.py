from __future__ import annotations

import io

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from app.api.v1.endpoints import ai


def test_legacy_ai_image_upload_rejects_oversized_payload_before_provider_call(
    client: TestClient,
    cardio_auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    """AI-REAUDIT-28 P1: /ai/analyze-xray endpoint was deleted (called
    non-existent AIManager method). Test now verifies _read_ai_upload_bounded
    rejects oversized payloads directly.
    """
    import io
    from fastapi import UploadFile

    monkeypatch.setattr(ai, "MAX_LEGACY_AI_UPLOAD_BYTES", 3)
    monkeypatch.setattr(ai, "AI_UPLOAD_READ_CHUNK_BYTES", 2)
    upload = UploadFile(file=io.BytesIO(b"abcd"), filename="oversized.png")

    with pytest.raises(HTTPException) as exc_info:
        import asyncio
        asyncio.get_event_loop().run_until_complete(ai._read_ai_upload_bounded(upload))

    assert exc_info.value.status_code == 413


@pytest.mark.asyncio
async def test_ai_upload_bounded_reader_rejects_oversized_payload(
    monkeypatch,
) -> None:
    monkeypatch.setattr(ai, "MAX_LEGACY_AI_UPLOAD_BYTES", 3)
    monkeypatch.setattr(ai, "AI_UPLOAD_READ_CHUNK_BYTES", 2)
    upload = UploadFile(file=io.BytesIO(b"abcd"), filename="voice.wav")

    with pytest.raises(HTTPException) as exc_info:
        await ai._read_ai_upload_bounded(upload)

    assert exc_info.value.status_code == 413
