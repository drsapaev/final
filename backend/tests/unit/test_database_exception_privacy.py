"""Real HTTP regression checks for the application's database handlers."""
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, OperationalError, StatementError

from app.core.exception_handlers import register_exception_handlers


SENTINEL = "SYNTHETIC-DATABASE-PRIVATE-32a4"
STATEMENT = f"SELECT '{SENTINEL}'"


@pytest.mark.parametrize(
    ("kind", "original", "expected_status", "error", "message", "detail"),
    [
        ("integrity", "UNIQUE constraint", 409, "integrity_error", "Нарушение уникальности данных", "Нарушение уникальности данных"),
        ("integrity", "FOREIGN KEY constraint", 409, "integrity_error", "Нарушение ссылочной целостности", "Нарушение ссылочной целостности"),
        ("integrity", "other", 409, "integrity_error", "Ошибка целостности данных", "Ошибка целостности данных"),
        ("operational", "other", 503, "database_operational_error", "Ошибка подключения к базе данных", "Попробуйте позже"),
        ("other", "other", 500, "database_error", "Ошибка базы данных", "Ошибка базы данных"),
    ],
)
def test_database_errors_keep_contract_without_exposing_details(
    kind, original, expected_status, error, message, detail, caplog
):
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/probe/{value}")
    def probe(value: str):
        orig = Exception(f"{original}: {SENTINEL}")
        if kind == "integrity":
            raise IntegrityError(STATEMENT, {"value": SENTINEL}, orig)
        if kind == "operational":
            raise OperationalError(STATEMENT, {"value": SENTINEL}, orig)
        raise StatementError(SENTINEL, STATEMENT, {"value": SENTINEL}, orig)

    with caplog.at_level(logging.DEBUG, logger="app.core.exception_handlers"):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(f"/probe/{SENTINEL}")

    assert response.status_code == expected_status
    assert response.json() == {"error": error, "message": message, "detail": detail}
    records = [r for r in caplog.records if r.name == "app.core.exception_handlers"]
    assert len(records) == 1
    assert records[0].levelno == logging.ERROR
    assert records[0].exc_info is None
    assert SENTINEL not in response.text
    handler_log = "\n".join(logging.Formatter().format(record) for record in records)
    assert SENTINEL not in handler_log
    assert STATEMENT not in handler_log
