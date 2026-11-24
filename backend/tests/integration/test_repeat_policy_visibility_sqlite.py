"""Exact persisted policy parsing and SQLite transaction reservation."""
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models.clinic import ClinicSettings
from app.services.repeat_policy_visibility import (
    RepeatPolicyBusy,
    RepeatPolicyUnavailable,
    parse_repeat_policy_value,
    read_sqlite_repeat_policy,
)


@pytest.fixture
def policy_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'synthetic_repeat_policy.db'}", connect_args={"timeout": 0.1})
    with engine.begin() as db:
        db.execute(text("CREATE TABLE clinic_settings (id INTEGER PRIMARY KEY, key TEXT UNIQUE NOT NULL, value JSON)"))
    yield engine
    engine.dispose()


@pytest.mark.parametrize("key,raw,expected", [
    ("repeat_visit_days", "21", 21),
    ("repeat_visit_days", '"21"', 21),
    ("repeat_visit_days", "2.100e1", 21),
    ("repeat_visit_discount", "0", 0),
    ("repeat_visit_discount", "100.0", 100),
])
def test_exact_json_policy_values(key, raw, expected):
    assert parse_repeat_policy_value(key, raw) == expected


@pytest.mark.parametrize("raw", [
    "0.99999999999999999999", "1e-1000", "1e9999999999999999999", "1e-9999999999999999999",
    "NaN", "Infinity", "true", "null",
    '"1.0000000000000000001"', "[]", "{}", "invalid", "1" * 129,
])
def test_raw_policy_values_never_round_into_valid_days(raw):
    with pytest.raises(RepeatPolicyUnavailable):
        parse_repeat_policy_value("repeat_visit_days", raw)


def test_absent_values_are_distinct_from_json_and_sql_null(policy_engine):
    with Session(policy_engine) as db:
        assert read_sqlite_repeat_policy(db) == {"repeat_visit_days": 21, "repeat_visit_discount": 0}
        db.rollback()
    for value in ("null", None):
        with policy_engine.begin() as db:
            db.execute(text("DELETE FROM clinic_settings"))
            db.execute(text("INSERT INTO clinic_settings(key,value) VALUES ('repeat_visit_days',:value)"), {"value": value})
        with Session(policy_engine) as db, pytest.raises(RepeatPolicyUnavailable):
            read_sqlite_repeat_policy(db)


def test_writer_reservation_serializes_absent_insert_until_root_rollback(policy_engine):
    with Session(policy_engine) as reader, Session(policy_engine) as writer:
        assert read_sqlite_repeat_policy(reader)["repeat_visit_days"] == 21
        with pytest.raises(DBAPIError) as error:
            writer.execute(text("INSERT INTO clinic_settings(key,value) VALUES ('repeat_visit_days','1')"))
        assert getattr(error.value.orig, "sqlite_errorcode", 0) & 0xff in {5, 6}
        writer.rollback()
        reader.rollback()
        writer.execute(text("INSERT INTO clinic_settings(key,value) VALUES ('repeat_visit_days','1')"))
        writer.commit()
    with Session(policy_engine) as db:
        assert read_sqlite_repeat_policy(db)["repeat_visit_days"] == 1


def test_conflicting_writer_fails_closed_and_retry_recovers(policy_engine):
    with Session(policy_engine) as writer, Session(policy_engine) as reader:
        writer.execute(text("INSERT INTO clinic_settings(key,value) VALUES ('repeat_visit_discount','20')"))
        with pytest.raises(RepeatPolicyBusy):
            read_sqlite_repeat_policy(reader)
        writer.commit()
        assert read_sqlite_repeat_policy(reader)["repeat_visit_discount"] == 20


def test_rejects_savepoint_and_unflushed_setting_mutations(policy_engine):
    with Session(policy_engine) as db:
        with db.begin_nested(), pytest.raises(RepeatPolicyUnavailable):
            read_sqlite_repeat_policy(db)
        db.rollback()
        db.add(ClinicSettings(key="repeat_visit_days", value=Decimal("1")))
        with pytest.raises(RepeatPolicyUnavailable):
            read_sqlite_repeat_policy(db)


def test_rejects_connection_managed_savepoint(policy_engine):
    with policy_engine.connect() as connection:
        outer = connection.begin()
        nested = connection.begin_nested()
        try:
            with Session(bind=connection, join_transaction_mode="rollback_only") as db:
                assert not db.in_nested_transaction()
                with pytest.raises(RepeatPolicyUnavailable):
                    read_sqlite_repeat_policy(db)
                with policy_engine.begin() as writer:
                    writer.execute(text("INSERT INTO clinic_settings(key,value) VALUES ('repeat_visit_days','1')"))
        finally:
            nested.rollback()
            outer.rollback()
