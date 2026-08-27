"""Offsite R2 uploader contracts (checkpoint #2772, directive items 4–7)."""
from __future__ import annotations

import hashlib
from unittest.mock import patch

import pytest

from app.services import r2_uploader
from app.services.r2_uploader import upload_file


class _FakeResponse:
    def __init__(self, headers):
        self.headers = headers
        self._read = False

    def read(self):
        if self._read:
            raise AssertionError("body consumed twice")
        self._read = True
        return b""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        monkeypatch.setenv(k, "test-" + k)
    monkeypatch.setenv("R2_BUCKET", "finalclinic-db-backups")


def _calls_log(http_return_factory):
    calls = []

    def fake_http(req, timeout=60):
        calls.append((req.get_method(), req.full_url))
        data = http_return_factory(len(calls), req)
        return data()

    return calls, fake_http


def test_zero_byte_refused_without_any_network(tmp_path, monkeypatch):
    f = tmp_path / "empty.db.gz"
    f.write_bytes(b"")

    def boom(req, timeout=60):  # noqa: ARG001
        raise AssertionError("network must not be touched")

    with patch.object(r2_uploader, "_http_request", boom):
        with pytest.raises(ValueError, match="zero-byte"):
            upload_file(key="daily/x", filepath=str(f))


def test_missing_artifact_refused(tmp_path):
    with pytest.raises(ValueError, match="artifact missing"):
        upload_file(key="daily/x", filepath=str(tmp_path / "ghost.db.gz"))


def test_not_configured_raises_clear_error(monkeypatch, tmp_path):
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        monkeypatch.delenv(k, raising=False)
    f = tmp_path / "real.db.gz"
    f.write_bytes(b"data")

    with pytest.raises(RuntimeError, match="not configured"):
        upload_file(key="daily/x", filepath=str(f))


def test_happy_path_put_then_head_verify(tmp_path):
    content = b"clinical-dump-bytes"
    f = tmp_path / "dump.db.gz"
    f.write_bytes(content)
    sha = hashlib.sha256(content).hexdigest()
    seen = []

    class Fake(_FakeResponse):
        pass

    def fake_http(req, timeout=60):
        seen.append((req.get_method(), req.full_url))
        if req.get_method() == "PUT":
            assert req.full_url.startswith(
                "https://test-R2_ACCOUNT_ID.r2.cloudflarestorage.com/"
                "finalclinic-db-backups/daily/"
            )
            assert hashlib.sha256(req.data).hexdigest() == sha
            return Fake({"ETag": '"etag123"'})
        assert req.get_method() == "HEAD"
        return Fake({
            "Content-Length": str(len(content)),
            "x-amz-meta-sha256": sha,
        })

    with patch.object(r2_uploader, "_http_request", fake_http):
        res = upload_file(key="daily/dump.db.gz", filepath=str(f))

    assert [m for m, _ in seen] == ["PUT", "HEAD"]
    assert res == {
        "key": "daily/dump.db.gz",
        "size": len(content),
        "sha256": sha,
        "etag": "etag123",
    }
