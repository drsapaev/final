from __future__ import annotations

from app.models.clinic import Branch, ClinicSettings


class _SessionContext:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, tb):
        return False


def test_ensure_admin_skips_initialized_instance_without_override(
    db_session,
    admin_user,
    monkeypatch,
):
    from app.scripts import ensure_admin as ensure_admin_module

    db_session.add(
        ClinicSettings(
            key="clinic_name",
            value="Initialized Clinic",
            category="clinic",
        )
    )
    db_session.add(
        Branch(
            name="Main Branch",
            code="main",
            timezone="Asia/Tashkent",
            capacity=50,
        )
    )
    db_session.commit()

    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_EMAIL", "ops@example.com")
    monkeypatch.setenv("ADMIN_FULL_NAME", "Ops Admin")
    monkeypatch.delenv("ENSURE_ADMIN_ALLOW_INITIALIZED", raising=False)
    monkeypatch.setattr(
        ensure_admin_module,
        "SessionLocal",
        lambda: _SessionContext(db_session),
    )

    result = ensure_admin_module.ensure_admin()

    assert result["skipped"] is True
    assert "explicit_ops_override" in result["reason"]
