"""Template mutation contract and SQLite partial-index behavior."""

import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.notifications import update_notification_template
from app.crud.notification import TemplateConcurrentUpdate
from app.crud.notification import crud_notification_template as crud
from app.models.notification import NotificationTemplate
from app.schemas.notification import (
    NotificationTemplateCreate,
    NotificationTemplateUpdate,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    NotificationTemplate.__table__.create(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


def create(db, name, type="reminder", active=True):
    return crud.create_atomic(
        db,
        obj_in=NotificationTemplateCreate(
            name=name, type=type, channel="email", template="hello", is_active=active
        ),
    )


def update(db, target, **fields):
    return crud.update_atomic(
        db, template_id=target.id, obj_in=NotificationTemplateUpdate(**fields)
    )


def test_create_activate_move_and_nullable_subject(db):
    a = create(db, "a")
    b = create(db, "b", active=False)
    assert db.get(NotificationTemplate, a.id).is_active
    update(db, b, is_active=True, subject=None)
    db.expire_all()
    assert not a.is_active and b.is_active and b.subject is None
    c = create(db, "c", type="other")
    update(db, b, type="other")
    db.expire_all()
    assert b.is_active and not c.is_active


@pytest.mark.parametrize("field", ["name", "type", "channel", "template", "is_active"])
def test_explicit_null_rejected_before_mutation(db, field):
    a = create(db, "a")
    b = create(db, "b", active=False)
    with pytest.raises(ValueError):
        update(
            db, b, is_active=True, **{field: None}
        ) if field != "is_active" else update(db, b, is_active=None)
    db.expire_all()
    assert a.is_active and not b.is_active


def test_sqlite_partial_index_and_rollback(db):
    active = create(db, "active")
    create(db, "inactive1", active=False)
    create(db, "inactive2", active=False)
    create(db, "taken", type="other")
    with pytest.raises(IntegrityError):
        create(db, "taken")
    assert db.get(NotificationTemplate, active.id).is_active
    db.add(
        NotificationTemplate(
            name="direct",
            type="reminder",
            channel="email",
            template="x",
            is_active=True,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_exhausted_update_retries_return_409(monkeypatch):
    def fail(*args, **kwargs):
        raise TemplateConcurrentUpdate()

    monkeypatch.setattr(crud, "update_atomic", fail)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            update_notification_template(
                1, NotificationTemplateUpdate(is_active=True), None
            )
        )
    assert exc.value.status_code == 409


def test_update_schema_marks_required_values_optional_but_not_nullable():
    schema = NotificationTemplateUpdate.model_json_schema()
    for field in ("name", "type", "channel", "template", "is_active"):
        assert field not in schema.get("required", [])
        assert schema["properties"][field]["type"] in {"string", "boolean"}
        assert "default" not in schema["properties"][field]
    assert {item["type"] for item in schema["properties"]["subject"]["anyOf"]} == {
        "string",
        "null",
    }
