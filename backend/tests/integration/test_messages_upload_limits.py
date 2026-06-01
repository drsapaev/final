from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.models.message import Message
from app.models.user import User
from app.services import messages_api_service


class _FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 1, 1, 12, 0, 0)
        if tz is not None:
            return value.replace(tzinfo=tz)
        return value

    @classmethod
    def utcnow(cls):
        return cls(2026, 1, 1, 12, 0, 0)


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


def test_chat_file_upload_uses_collision_resistant_storage_name(
    client: TestClient,
    patient_token: str,
    test_doctor_user: User,
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(messages_api_service, "datetime", _FixedDatetime)

    first_response = client.post(
        "/api/v1/messages/upload",
        headers={"Authorization": f"Bearer {patient_token}"},
        data={"recipient_id": str(test_doctor_user.id)},
        files={"file": ("report.pdf", b"first", "application/pdf")},
    )
    second_response = client.post(
        "/api/v1/messages/upload",
        headers={"Authorization": f"Bearer {patient_token}"},
        data={"recipient_id": str(test_doctor_user.id)},
        files={"file": ("report.pdf", b"second", "application/pdf")},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["content"] != second_response.json()["content"]

    uploaded_files = sorted((tmp_path / "uploads" / "chat").iterdir())
    assert {item.read_bytes() for item in uploaded_files} == {b"first", b"second"}


def test_chat_file_download_authorizes_any_matching_message_candidate(
    client: TestClient,
    db_session,
    admin_user: User,
    registrar_user: User,
    test_doctor_user: User,
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    filename = "20260101_120000_report.pdf"
    upload_dir = tmp_path / "uploads" / "chat"
    upload_dir.mkdir(parents=True)
    (upload_dir / filename).write_bytes(b"report")

    download_url = f"/api/v1/messages/download/{filename}?name=report.pdf"
    db_session.add(
        Message(
            sender_id=admin_user.id,
            recipient_id=registrar_user.id,
            message_type="file",
            content=download_url,
        )
    )
    db_session.add(
        Message(
            sender_id=admin_user.id,
            recipient_id=test_doctor_user.id,
            message_type="file",
            content=download_url,
        )
    )
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: test_doctor_user
    try:
        response = client.get(f"/api/v1/messages/download/{filename}")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.content == b"report"
