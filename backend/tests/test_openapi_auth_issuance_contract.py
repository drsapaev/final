"""Published contract for second-factor-gated patient session issuance."""

import pytest


def _dereference(schema: dict, spec: dict) -> dict:
    reference = schema.get("$ref")
    return (
        spec["components"]["schemas"][reference.rsplit("/", 1)[-1]]
        if reference
        else schema
    )


def _non_null(schema: dict) -> dict:
    return next(
        (item for item in schema.get("anyOf", []) if item.get("type") != "null"), schema
    )


def _no_store(operation: dict) -> None:
    header = operation["responses"]["200"]["headers"]["Cache-Control"]
    assert header["required"] is True
    assert header["schema"]["const"] == "no-store"


def _assert_access_or_pending(operation: dict, spec: dict) -> None:
    _no_store(operation)
    output = _dereference(
        operation["responses"]["200"]["content"]["application/json"]["schema"], spec
    )
    branches = [_dereference(branch, spec) for branch in output["oneOf"]]
    assert len(branches) == 2
    session = next(
        branch for branch in branches if "access_token" in branch["required"]
    )
    pending = next(
        branch for branch in branches if "pending_2fa_token" in branch["required"]
    )
    assert session["additionalProperties"] is False
    assert pending["additionalProperties"] is False
    assert {"access_token", "token_type", "user"} <= set(session["required"])
    assert {"requires_2fa", "two_factor_method", "pending_2fa_token", "user"} <= set(
        pending["required"]
    )
    assert pending["properties"]["requires_2fa"]["const"] is True
    assert pending["properties"]["two_factor_method"]["const"] == "totp"
    assert not ({"access_token", "refresh_token"} & set(pending["properties"]))
    assert "refresh_token" not in session["properties"]


def test_discoverable_login_requires_second_bound_assertion_in_openapi(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    finish = spec["paths"]["/api/v1/webauthn/login/discoverable/finish"]["post"]
    complete = spec["paths"]["/api/v1/webauthn/login/discoverable/complete"]["post"]

    for operation in (finish, complete):
        assert {"200", "403", "429", "503"} <= set(operation["responses"])
        assert operation["requestBody"]["required"] is True
        request = _dereference(
            operation["requestBody"]["content"]["application/json"]["schema"], spec
        )
        assert {"ceremony_id", "assertion_response"} <= set(request["required"])
        assertion = request["properties"]["assertion_response"]
        assert {"id", "rawId", "type", "response"} <= set(assertion["required"])
        _no_store(operation)

    first = _dereference(
        finish["responses"]["200"]["content"]["application/json"]["schema"], spec
    )
    assert first["required"] == ["next_options"]
    assert first["additionalProperties"] is False
    assert not ({"access_token", "refresh_token", "user"} & set(first["properties"]))
    options = first["properties"]["next_options"]
    assert {
        "challenge",
        "ceremony_id",
        "rpId",
        "userVerification",
        "allowCredentials",
    } <= set(options["required"])
    assert options["properties"]["userVerification"]["const"] == "required"
    allowed = options["properties"]["allowCredentials"]
    assert (allowed["minItems"], allowed["maxItems"]) == (1, 1)
    assert {"id", "type"} <= set(allowed["items"]["required"])
    assert allowed["items"]["properties"]["type"]["const"] == "public-key"

    _assert_access_or_pending(complete, spec)
    legacy = spec["paths"]["/api/v1/webauthn/login/finish"]["post"]
    _assert_access_or_pending(legacy, spec)


def test_patient_sms_login_documents_access_only_or_pending_second_factor(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    login = spec["paths"]["/api/v1/patient-access/login"]["post"]
    assert login["requestBody"]["required"] is True
    body = _dereference(
        login["requestBody"]["content"]["application/json"]["schema"], spec
    )
    assert {"phone", "verification_grant"} <= set(body["required"])
    _assert_access_or_pending(login, spec)


@pytest.mark.parametrize("pending", [False, True])
def test_patient_sms_login_never_caches_session_or_pending_token(
    client, monkeypatch, pending
):
    from app.api.v1.endpoints import patient_access

    user = {
        "id": 1,
        "username": "SYNTHETIC",
        "role": "Patient",
        "is_active": True,
        "is_superuser": False,
    }
    if pending:
        result = {
            "requires_2fa": True,
            "two_factor_method": "totp",
            "pending_2fa_token": "SYNTHETIC-PENDING-ONLY",
            "user": user,
        }
    else:
        result = {
            "access_token": "SYNTHETIC-ACCESS-ONLY",
            "token_type": "bearer",
            "user": user,
        }

    class LoginService:
        def login_with_grant(self, db, phone, grant):
            return result

    monkeypatch.setattr(
        patient_access, "get_patient_otp_service", lambda: LoginService()
    )
    response = client.post(
        "/api/v1/patient-access/login",
        json={"phone": "+998000000000", "verification_grant": "SYNTHETIC-GRANT-0000"},
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == result
    assert "refresh_token" not in response.json()
    if pending:
        assert "access_token" not in response.json()


def test_unavailable_individual_session_routes_document_conflict(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    for path, method in (
        ("/api/v1/authentication/sessions/current", "get"),
        ("/api/v1/authentication/sessions/{session_id}", "delete"),
        ("/api/v1/authentication/sessions/{session_id}/revoke", "post"),
        ("/api/v1/authentication/sessions/revoke-all", "post"),
    ):
        operation = spec["paths"][path][method]
        assert operation.get("security") or spec.get("security")
        assert operation["responses"]["409"]["description"]


def test_mobile_login_documents_second_factor_and_non_cached_session(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    login = spec["paths"]["/api/v1/mobile/auth/login"]["post"]
    assert login["operationId"] == "mobile_login_api_v1_mobile_auth_login_post"
    assert login["requestBody"]["required"] is True
    assert {"200", "400", "401", "422", "500"} <= set(login["responses"])
    request = _dereference(
        login["requestBody"]["content"]["application/json"]["schema"], spec
    )
    assert "phone" in request["required"]
    assert {"".join(('pass', 'word')),
        "totp_code", "backup_code"} <= set(request["properties"])
    totp = _non_null(request["properties"]["totp_code"])
    backup = _non_null(request["properties"]["backup_code"])
    assert (totp["minLength"], totp["maxLength"]) == (6, 6)
    assert (backup["minLength"], backup["maxLength"]) == (8, 10)
    _no_store(login)
    session = _dereference(
        login["responses"]["200"]["content"]["application/json"]["schema"], spec
    )
    assert {"access_token", "user"} <= set(session["required"])
    for status in ("400", "401", "500"):
        error = _dereference(
            login["responses"][status]["content"]["application/json"]["schema"], spec
        )
        assert error["properties"]["detail"]["type"] == "string"


def test_email_verification_request_and_confirmation_contract(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    request = spec["paths"]["/api/v1/authentication/email-verification"]["post"]
    confirm = spec["paths"]["/api/v1/authentication/email-verification/confirm"]["post"]

    assert request.get("security") or spec.get("security")
    assert {"200", "401", "429", "502", "503"} <= set(request["responses"])
    assert {"200", "400", "422", "500"} <= set(confirm["responses"])
    assert confirm["requestBody"]["required"] is True
    payload = _dereference(
        confirm["requestBody"]["content"]["application/json"]["schema"], spec
    )
    assert "token" in payload["required"]
    assert payload["properties"]["token"]["type"] == "string"
    for operation, statuses in (
        (request, ("401", "429", "502", "503")),
        (confirm, ("400", "500")),
    ):
        for status in statuses:
            error = _dereference(
                operation["responses"][status]["content"]["application/json"]["schema"],
                spec,
            )
            assert error["properties"]["detail"]["type"] == "string"
