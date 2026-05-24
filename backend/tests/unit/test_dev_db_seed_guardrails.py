from __future__ import annotations

import pytest

from app.scripts.reset_dev_db import (
    DevDatabaseSafetyError,
    build_preflight,
    require_confirm_db_name,
)


LOCAL_URL = "postgresql+psycopg://clinic@localhost:5432/clinic_dev"


def test_preflight_accepts_local_postgres_dev_db(monkeypatch):
    monkeypatch.setenv("ENV", "dev")

    preflight = build_preflight(LOCAL_URL, mode="schema", seed_profile="demo")

    assert preflight.driver == "postgresql+psycopg"
    assert preflight.host == "localhost"
    assert preflight.database == "clinic_dev"
    assert preflight.username == "clinic"


@pytest.mark.parametrize("env_name", ["ENV", "APP_ENV", "ENVIRONMENT"])
@pytest.mark.parametrize("env_value", ["prod", "production"])
def test_preflight_refuses_production_environment(monkeypatch, env_name, env_value):
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv(env_name, env_value)

    with pytest.raises(DevDatabaseSafetyError, match="production environment"):
        build_preflight(LOCAL_URL, mode="schema")


def test_preflight_refuses_sqlite(monkeypatch):
    monkeypatch.setenv("ENV", "dev")

    with pytest.raises(DevDatabaseSafetyError, match="SQLite"):
        build_preflight("sqlite:///clinic.db", mode="schema")


def test_preflight_refuses_non_postgres(monkeypatch):
    monkeypatch.setenv("ENV", "dev")

    with pytest.raises(DevDatabaseSafetyError, match="non-PostgreSQL"):
        build_preflight("mysql+pymysql://clinic@localhost/clinic_dev", mode="schema")


@pytest.mark.parametrize(
    "database",
    ["prod", "production", "clinic_prod", "clinic-prod", "clinic_production"],
)
def test_preflight_refuses_suspicious_database_names(monkeypatch, database):
    monkeypatch.setenv("ENV", "dev")

    with pytest.raises(DevDatabaseSafetyError, match="suspicious database"):
        build_preflight(
            f"postgresql+psycopg://clinic@localhost:5432/{database}",
            mode="schema",
        )


def test_preflight_refuses_remote_host_without_explicit_flag(monkeypatch):
    monkeypatch.setenv("ENV", "dev")

    with pytest.raises(DevDatabaseSafetyError, match="remote database host"):
        build_preflight(
            "postgresql+psycopg://clinic@db.example.test:5432/clinic_dev",
            mode="schema",
        )


def test_preflight_allows_remote_host_with_explicit_flag(monkeypatch):
    monkeypatch.setenv("ENV", "dev")

    preflight = build_preflight(
        "postgresql+psycopg://clinic@db.example.test:5432/clinic_dev",
        mode="schema",
        allow_remote_dev_db=True,
    )

    assert preflight.host == "db.example.test"


def test_confirm_db_name_must_match_parsed_database(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    preflight = build_preflight(LOCAL_URL, mode="schema")

    with pytest.raises(DevDatabaseSafetyError, match="confirm-db-name"):
        require_confirm_db_name(preflight, "clinic_test")

    require_confirm_db_name(preflight, "clinic_dev")
