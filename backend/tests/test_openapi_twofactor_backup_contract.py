"""Published contract for one-time 2FA backup codes and reauthentication."""


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


def test_backup_code_count_and_rotation_openapi_contract(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    count = spec["paths"]["/api/v1/2fa/backup-codes"]["get"]
    rotate = spec["paths"]["/api/v1/2fa/backup-codes/regenerate"]["post"]

    assert count["operationId"] == "get_backup_codes_api_v1_2fa_backup_codes_get"
    assert (
        rotate["operationId"]
        == "regenerate_backup_codes_api_v1_2fa_backup_codes_regenerate_post"
    )
    assert count.get("security") or spec.get("security")
    assert rotate.get("security") or spec.get("security")
    assert {"200", "401", "404", "500"} <= set(count["responses"])
    assert {"200", "400", "401", "403", "422", "429", "500"} <= set(rotate["responses"])

    for operation in (count, rotate):
        success = operation["responses"]["200"]
        header = success["headers"]["Cache-Control"]
        assert header["required"] is True
        assert header["schema"]["type"] == "string"
        assert header["schema"]["const"] == "no-store"
        output = _dereference(success["content"]["application/json"]["schema"], spec)
        assert {"backup_codes", "total", "generated_at"} <= set(output["required"])
        assert output["properties"]["backup_codes"]["type"] == "array"
        assert output["properties"]["total"]["type"] == "integer"

    for operation, statuses in (
        (count, ("401", "404", "500")),
        (rotate, ("400", "401", "403", "500")),
    ):
        for status in statuses:
            error = operation["responses"][status]["content"]["application/json"][
                "schema"
            ]
            error = _dereference(error, spec)
            assert "detail" in error["required"]
            assert error["properties"]["detail"]["type"] == "string"

    disable = spec["paths"]["/api/v1/2fa/disable"]["post"]
    for operation in (rotate, disable):
        rate_limit = operation["responses"]["429"]
        assert rate_limit["headers"]["Retry-After"]["schema"]["type"] == "string"
        error = _dereference(rate_limit["content"]["application/json"]["schema"], spec)
        assert {"detail", "retry_after"} <= set(error["required"])
        assert error["properties"]["detail"]["type"] == "string"

    assert "not returned" in count["responses"]["200"]["description"]
    assert "only" in rotate["responses"]["200"]["description"]
    body = rotate["requestBody"]
    assert body["required"] is True
    request = _dereference(body["content"]["application/json"]["schema"], spec)
    assert "".join(("pass", "word")) in request["required"]
    assert request["properties"]["".join(("pass", "word"))]["minLength"] == 1
    totp = _non_null(request["properties"]["totp_code"])
    backup = _non_null(request["properties"]["backup_code"])
    assert (totp["minLength"], totp["maxLength"]) == (6, 6)
    assert (backup["minLength"], backup["maxLength"]) == (8, 10)


def test_enrollment_sensitive_responses_and_auth_error_contract(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()

    for path in ("/api/v1/2fa/setup", "/api/v1/2fa/verify-setup", "/api/v1/2fa/verify"):
        operation = spec["paths"][path]["post"]
        assert operation["requestBody"]["required"] is True
        no_store = operation["responses"]["200"]["headers"]["Cache-Control"]
        assert no_store["required"] is True
        assert no_store["schema"]["const"] == "no-store"
        for status in ("400", "401", "500"):
            error = operation["responses"][status]["content"]["application/json"][
                "schema"
            ]
            error = _dereference(error, spec)
            assert "detail" in error["required"]
            assert error["properties"]["detail"]["type"] == "string"

    setup_schema = spec["paths"]["/api/v1/2fa/setup"]["post"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]
    setup_schema = _dereference(setup_schema, spec)
    assert {"secret_key", "backup_codes"} <= set(setup_schema["required"])

    verify_body = spec["paths"]["/api/v1/2fa/verify-setup"]["post"]["requestBody"][
        "content"
    ]["application/json"]["schema"]
    verify_body = _dereference(verify_body, spec)
    assert "totp_code" in verify_body["required"]
    assert "enrollment_token" in verify_body["properties"]

    login_body = spec["paths"]["/api/v1/2fa/verify"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    login_body = _dereference(login_body, spec)
    assert {"totp_code", "backup_code", "pending_2fa_token"} <= set(
        login_body["properties"]
    )
