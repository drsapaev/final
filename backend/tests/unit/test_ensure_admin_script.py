from __future__ import annotations

from types import SimpleNamespace

from app.scripts import ensure_admin as ensure_admin_script


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


class _FakeExecuteResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return _FakeScalarResult(self._value)


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.added = []
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query):  # noqa: ARG002
        if not self._responses:
            raise AssertionError("Unexpected query execution with no prepared response")
        return _FakeExecuteResult(self._responses.pop(0))

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1


def _clear_admin_env(monkeypatch):
    for name in (
        "ADMIN_USERNAME",
        "ADMIN_PASSWORD",
        "ADMIN_EMAIL",
        "ADMIN_FULL_NAME",
        "ADMIN_ALLOW_UPDATE",
        "ADMIN_RESET_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)


def test_ensure_admin_skips_existing_user_without_admin_allow_update(monkeypatch):
    _clear_admin_env(monkeypatch)
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("ADMIN_FULL_NAME", "Administrator")

    existing_user = SimpleNamespace(
        id=7,
        username="admin",
        email="admin@example.com",
        full_name="Old Name",
        role="Registrar",
        is_active=False,
        hashed_password="old-hash",
    )
    fake_session = _FakeSession([existing_user])
    monkeypatch.setattr(ensure_admin_script, "SessionLocal", lambda: fake_session)

    result = ensure_admin_script.ensure_admin()

    assert result["skipped"] is True
    assert result["reason"] == "existing_user_found_requires_ADMIN_ALLOW_UPDATE"
    assert existing_user.role == "Registrar"
    assert existing_user.is_active is False
    assert existing_user.full_name == "Old Name"
    assert fake_session.commits == 0


def test_ensure_admin_updates_existing_user_when_admin_allow_update_enabled(monkeypatch):
    _clear_admin_env(monkeypatch)
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "new-secret")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("ADMIN_FULL_NAME", "Administrator")
    monkeypatch.setenv("ADMIN_ALLOW_UPDATE", "1")
    monkeypatch.setenv("ADMIN_RESET_PASSWORD", "1")

    existing_user = SimpleNamespace(
        id=8,
        username="admin",
        email="admin@example.com",
        full_name="Legacy Admin",
        role="Registrar",
        is_active=False,
        hashed_password="old-hash",
    )
    fake_session = _FakeSession([existing_user])
    monkeypatch.setattr(ensure_admin_script, "SessionLocal", lambda: fake_session)
    monkeypatch.setattr(ensure_admin_script, "_hash_or_plain", lambda pw: f"hashed::{pw}")

    result = ensure_admin_script.ensure_admin()

    assert result["updated"] is True
    assert existing_user.role == "Admin"
    assert existing_user.is_active is True
    assert existing_user.full_name == "Administrator"
    assert existing_user.hashed_password == "hashed::new-secret"
    assert fake_session.commits == 1


def test_ensure_admin_skips_existing_match_resolved_by_email_without_admin_allow_update(monkeypatch):
    _clear_admin_env(monkeypatch)
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("ADMIN_FULL_NAME", "Administrator")

    existing_user = SimpleNamespace(
        id=9,
        username="legacy-admin",
        email="admin@example.com",
        full_name="Legacy Admin",
        role="Registrar",
        is_active=True,
        hashed_password="old-hash",
    )
    fake_session = _FakeSession([None, existing_user, existing_user])
    monkeypatch.setattr(ensure_admin_script, "SessionLocal", lambda: fake_session)

    result = ensure_admin_script.ensure_admin()

    assert result["skipped"] is True
    assert result["reason"] == "existing_user_found_requires_ADMIN_ALLOW_UPDATE"
    assert existing_user.username == "legacy-admin"
    assert existing_user.role == "Registrar"
    assert fake_session.commits == 0


def test_ensure_admin_creates_user_when_missing(monkeypatch):
    _clear_admin_env(monkeypatch)
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "new-secret")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("ADMIN_FULL_NAME", "Administrator")
    fake_session = _FakeSession([None, None, None])
    monkeypatch.setattr(ensure_admin_script, "SessionLocal", lambda: fake_session)
    monkeypatch.setattr(ensure_admin_script, "_hash_or_plain", lambda pw: f"hashed::{pw}")

    result = ensure_admin_script.ensure_admin()

    assert result["created"] is True
    assert fake_session.commits == 1
    assert len(fake_session.added) == 1
    created_user = fake_session.added[0]
    assert created_user.username == "admin"
    assert created_user.role == "Admin"
    assert created_user.hashed_password == "hashed::new-secret"
