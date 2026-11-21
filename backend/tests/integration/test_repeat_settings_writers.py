"""Exact JSON and authorization for repeat-policy configuration writers."""
from decimal import Decimal

import pytest

from app.models.clinic import ClinicSettings
from app.services.repeat_policy_input import validate_repeat_setting

REGISTRAR = "/api/v1/admin/benefit-settings"
SETTINGS = "/api/v1/admin/clinic/settings"


@pytest.fixture
def policy(db_session):
    row = db_session.query(ClinicSettings).filter_by(key="repeat_visit_days").first()
    if row is None:
        row = ClinicSettings(key="repeat_visit_days", value=21, category="benefits")
        db_session.add(row)
    else:
        row.value = 21
    db_session.commit()
    return row.id


def request(client, headers, route, value):
    if route == "registrar":
        return client.post(REGISTRAR, headers=headers, content=f'{{"repeat_visit_days":{value}}}')
    if route == "create":
        return client.post(SETTINGS, headers=headers, content=f'{{"key":"repeat_visit_discount","value":{value}}}')
    if route == "update":
        return client.put(SETTINGS + "/repeat_visit_days", headers=headers, content=f'{{"value":{value}}}')
    return client.put(SETTINGS, headers=headers, content=f'{{"settings":{{"repeat_visit_days":{value},"clinic_name":"SYNTHETIC-change"}}}}')


@pytest.mark.parametrize("route", ["registrar", "create", "update", "batch"])
@pytest.mark.parametrize("value", ["0.99999999999999999999", "1e-1000", '"1.000000000000000001"', "true", "NaN"])
def test_original_noninteger_json_is_rejected_without_settings_writes(
    client, admin_auth_headers, db_session, policy, route, value
):
    before = {row.key: row.value for row in db_session.query(ClinicSettings).all()}
    response = request(client, {**admin_auth_headers, "Content-Type": "application/json"}, route, value)
    assert response.status_code == 422, response.text
    db_session.expire_all()
    assert {row.key: row.value for row in db_session.query(ClinicSettings).all()} == before


@pytest.mark.parametrize("body,expected", [
    ('{"value":1,"value":0.99999999999999999999}', 422),
    ('{"value":0.99999999999999999999,"value":1}', 200),
    ('{"value":1.0}', 200),
    ('{"value":"2"}', 200),
])
def test_duplicate_json_uses_same_last_key_as_starlette(client, admin_auth_headers, policy, body, expected):
    response = client.put(SETTINGS + "/repeat_visit_days", content=body,
                          headers={**admin_auth_headers, "Content-Type": "application/json"})
    assert response.status_code == expected, response.text


def test_repeat_setting_request_has_bounded_size(client, admin_auth_headers, db_session, policy):
    response = client.put(SETTINGS + "/repeat_visit_days", headers=admin_auth_headers,
                          json={"value": 10, "description": "x" * 65536})
    assert response.status_code == 422
    db_session.expire_all()
    assert db_session.get(ClinicSettings, policy).value == 21


@pytest.mark.parametrize("key,value", [
    ("repeat_visit_days", True), ("repeat_visit_days", Decimal("1e-1000")),
    ("repeat_visit_discount", Decimal("100.000000000000000001")),
    ("repeat_visit_discount", -1), ("repeat_visit_days", 1.0),
])
def test_direct_settings_validation_rejects_invalid_values(key, value):
    with pytest.raises(ValueError):
        validate_repeat_setting(key, value)


def test_valid_benefit_settings_and_unrelated_clinic_settings_work(client, admin_auth_headers, db_session, policy):
    response = client.post(REGISTRAR, headers=admin_auth_headers, json={
        "repeat_visit_days": 30, "repeat_visit_discount": 15,
        "benefit_consultation_free": True, "all_free_auto_approve": False})
    assert response.status_code == 200, response.text
    response = client.put(SETTINGS, headers=admin_auth_headers,
                          json={"settings": {"clinic_name": "SYNTHETIC-policy-test"}})
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert db_session.query(ClinicSettings).filter_by(key="repeat_visit_days").one().value == 30


def test_deactivated_admin_cannot_write_policy(client, admin_user, admin_auth_headers, db_session, policy):
    admin_user.is_active = False
    db_session.commit()
    response = client.put(SETTINGS + "/repeat_visit_days", headers=admin_auth_headers, json={"value": 5})
    assert response.status_code in {401, 403}, response.text
    db_session.expire_all()
    assert db_session.get(ClinicSettings, policy).value == 21


def test_only_reviewed_global_settings_handlers_declare_admin_replay():
    from starlette.requests import Request

    from app.api.v1.endpoints import admin_clinic
    from app.api.v1.endpoints.registrar_wizard import _settings
    from app.main import app
    from app.middleware.idempotency_middleware import IdempotencyMiddleware

    for handler in (admin_clinic.update_clinic_settings_batch, admin_clinic.update_clinic_setting,
                    admin_clinic.create_clinic_setting, _settings.update_benefit_settings):
        assert handler.idempotency_replay_global_roles == ("Admin",)
    assert not hasattr(_settings.get_benefit_settings, "idempotency_replay_global_roles")
    expected = {
        ("PUT", "/api/v1/admin/clinic/settings"), ("POST", "/api/v1/admin/clinic/settings"),
        ("PUT", "/api/v1/admin/clinic/settings/{key}"), ("POST", "/api/v1/admin/benefit-settings"),
    }
    def effective_routes(routes):
        for route in routes:
            children = getattr(route, "effective_candidates", None)
            if callable(children):
                yield from effective_routes(children())
            else:
                yield route

    registered = {(method, route.path) for route in effective_routes(app.routes)
                  for method in getattr(route, "methods", ()) or ()
                  if getattr(getattr(route, "endpoint", None), "idempotency_replay_global_roles", None) == ("Admin",)}
    assert expected <= registered
    middleware = IdempotencyMiddleware(app=None)
    for method, path in expected:
        scope = {"type": "http", "method": method, "path": path.replace("{key}", "repeat_visit_days"),
                 "root_path": "", "headers": [], "query_string": b"", "app": app}
        assert middleware._endpoint_allowed_roles(Request(scope)) == frozenset({"admin"})


@pytest.mark.parametrize("role,superuser,allowed", [
    ("Admin", False, True), ("Nurse", True, True), ("SuperAdmin", False, False),
])
def test_global_replay_marker_matches_live_role_gate(
    client, admin_user, admin_auth_headers, db_session, policy, role, superuser, allowed
):
    admin_user.role = role
    admin_user.is_superuser = superuser
    db_session.commit()
    response = client.put(SETTINGS + "/repeat_visit_days", headers=admin_auth_headers, json={"value": 30})
    assert response.status_code == (200 if allowed else 403), response.text


@pytest.mark.parametrize("route", ["registrar", "update", "batch"])
def test_expiry_immediately_before_commit_rolls_back_settings(
    client, admin_auth_headers, db_session, policy, monkeypatch, route
):
    from app.services import repeat_policy_input
    from app.services.profile_contact_security import ProfileBearerInvalid

    def expired(_context):
        raise ProfileBearerInvalid("synthetic expired session")

    monkeypatch.setattr(repeat_policy_input, "check_bearer_expiry", expired)
    before = {row.key: row.value for row in db_session.query(ClinicSettings).all()}
    response = request(client, {**admin_auth_headers, "Content-Type": "application/json"}, route, "30")
    assert response.status_code == 401, response.text
    db_session.expire_all()
    assert {row.key: row.value for row in db_session.query(ClinicSettings).all()} == before


def test_sqlite_writer_contention_retries_without_partial_settings(tmp_path):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.api.deps import get_db
    from app.db.base_class import Base
    from app.main import app
    from app.models.user import User
    from tests.conftest import mint_access_token

    engine = create_engine(f"sqlite:///{tmp_path / 'synthetic_policy.db'}",
                           connect_args={"check_same_thread": False, "timeout": 0.15})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    with sessions() as db:
        actor = User(username="synthetic_sqlite_admin", hashed_password="!synthetic", role="Admin", is_active=True)
        db.add_all([actor, ClinicSettings(key="repeat_visit_days", value=21)])
        db.commit()
        token = mint_access_token(actor)

    def database():
        with sessions() as db:
            yield db

    old = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = database
    try:
        with TestClient(app) as test_client, engine.connect() as blocker:
            blocker.exec_driver_sql("BEGIN IMMEDIATE")
            path = SETTINGS + "/repeat_visit_days"
            headers = {"Authorization": f"Bearer {token}"}
            response = test_client.put(path, headers=headers, json={"value": 30})
            assert response.status_code == 409, response.text
            blocker.rollback()
            with sessions() as db:
                assert db.query(ClinicSettings).filter_by(key="repeat_visit_days").one().value == 21
            response = test_client.put(path, headers=headers, json={"value": 30})
            assert response.status_code == 200, response.text
            with sessions() as db:
                assert db.query(ClinicSettings).filter_by(key="repeat_visit_days").one().value == 30
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old)
        engine.dispose()
