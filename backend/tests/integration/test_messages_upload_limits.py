from __future__ import annotations

from fastapi.testclient import TestClient

from app.models.user import User
from app.services import messages_api_service


def test_chat_file_upload_rejects_oversized_payload_before_write(
    client: TestClient,
    patient_token: str,
    test_doctor_user: User,
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(messages_api_service, "MAX_CHAT_UPLOAD_BYTES", 3)
    monkeypatch.setattr(messages_api_service, "UPLOAD_READ_CHUNK_BYTES", 2)

    response = client.post(
        "/api/v1/messages/upload",
        headers={"Authorization": f"Bearer {patient_token}"},
        data={"recipient_id": str(test_doctor_user.id)},
        files={"file": ("oversized.txt", b"abcd", "text/plain")},
    )

    assert response.status_code == 413
    assert not (tmp_path / "uploads").exists()


def test_voice_message_rejects_oversized_payload_before_write(
    client: TestClient,
    patient_token: str,
    test_doctor_user: User,
    monkeypatch,
    tmp_path,
) -> None:
    from app.utils import audio

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(audio, "MAX_AUDIO_SIZE", 3)
    monkeypatch.setattr(messages_api_service, "UPLOAD_READ_CHUNK_BYTES", 2)

    response = client.post(
        "/api/v1/messages/send-voice",
        headers={"Authorization": f"Bearer {patient_token}"},
        data={"recipient_id": str(test_doctor_user.id)},
        files={"audio_file": ("voice.mp3", b"abcd", "audio/mpeg")},
    )

    assert response.status_code == 413
    assert not (tmp_path / "uploads").exists()
