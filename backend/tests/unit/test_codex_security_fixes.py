from __future__ import annotations

import io
import zipfile
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.schemas.file_system import FilePermissionEnum
from app.schemas.webhook import WebhookCreate, WebhookEventTypeEnum, WebhookUpdate
from app.services import file_system_service as file_system_module
from app.services.file_system_service import FileSystemService
from app.utils import url_security
from app.utils.url_security import validate_public_http_url


def _service(tmp_path, monkeypatch) -> FileSystemService:
    monkeypatch.setenv("FILE_STORAGE_PATH", str(tmp_path / "files"))
    monkeypatch.setenv("TEMP_STORAGE_PATH", str(tmp_path / "temp"))
    return FileSystemService()


def _file(permission: FilePermissionEnum = FilePermissionEnum.PRIVATE):
    return SimpleNamespace(id=42, owner_id=1, permission=permission)


def test_share_token_presence_does_not_grant_other_users_access(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    active_token_share_for_someone_else = SimpleNamespace(
        shared_with_user_id=99,
        access_token="active-token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    monkeypatch.setattr(
        file_system_module.file_share,
        "get_file_shares",
        lambda db, file_id: [active_token_share_for_someone_else],
    )

    assert service._check_file_access(object(), _file(), user_id=2) is False


def test_direct_unexpired_share_still_grants_access(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    direct_share = SimpleNamespace(
        shared_with_user_id=2,
        access_token="token-for-a-link",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    monkeypatch.setattr(
        file_system_module.file_share,
        "get_file_shares",
        lambda db, file_id: [direct_share],
    )

    assert service._check_file_access(object(), _file(), user_id=2) is True


def test_expired_direct_share_does_not_grant_access(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    expired_direct_share = SimpleNamespace(
        shared_with_user_id=2,
        access_token="expired-token",
        expires_at=datetime.utcnow() - timedelta(seconds=1),
    )
    monkeypatch.setattr(
        file_system_module.file_share,
        "get_file_shares",
        lambda db, file_id: [expired_direct_share],
    )

    assert service._check_file_access(object(), _file(), user_id=2) is False


def test_webhook_schema_rejects_private_network_urls(monkeypatch):
    monkeypatch.setattr(
        url_security.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 443))],
    )

    with pytest.raises(ValueError, match="URL host is not allowed"):
        WebhookCreate(
            name="internal",
            url="https://example.test/hook",
            events=[WebhookEventTypeEnum.PATIENT_CREATED],
        )


def test_webhook_schema_accepts_public_urls(monkeypatch):
    monkeypatch.setattr(
        url_security.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 443))],
    )

    webhook = WebhookCreate(
        name="external",
        url="https://example.test/hook",
        events=[WebhookEventTypeEnum.PATIENT_CREATED],
    )
    update = WebhookUpdate(url="https://example.test/updated")

    assert str(webhook.url).startswith("https://example.test/")
    assert str(update.url).startswith("https://example.test/")


def test_public_url_validator_rejects_credentials(monkeypatch):
    monkeypatch.setattr(
        url_security.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 443))],
    )

    with pytest.raises(ValueError, match="credentials"):
        validate_public_http_url("https://user:pass@example.test/hook")


def test_safe_zip_extract_rejects_path_traversal(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zipf:
        zipf.writestr("../evil.txt", "owned")
    archive.seek(0)

    with zipfile.ZipFile(archive) as zipf, pytest.raises(HTTPException) as exc:
        service._safe_extract_zip(zipf, str(tmp_path / "extract"))

    assert exc.value.status_code == 400


def test_safe_zip_extract_rejects_uncompressed_size_limit(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    service.max_import_uncompressed_size = 10
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zipf:
        zipf.writestr("large.txt", "x" * 11)
    archive.seek(0)

    with zipfile.ZipFile(archive) as zipf, pytest.raises(HTTPException) as exc:
        service._safe_extract_zip(zipf, str(tmp_path / "extract"))

    assert exc.value.status_code == 413
