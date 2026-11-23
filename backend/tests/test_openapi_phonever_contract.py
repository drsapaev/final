"""The phone and reset contracts expose body-only inputs and bounded responses."""

from app.main import app


def _ref_name(schema: dict) -> str:
    return schema["$ref"].rsplit("/", 1)[-1]


def test_phone_verification_operations_publish_body_and_auth_contract():
    schema = app.openapi()
    paths = schema["paths"]
    expected = {
        "/api/v1/phone-verification/send-code": ("post", "SendVerificationCodeRequest", "PhoneVerificationSendResponse"),
        "/api/v1/phone-verification/status": ("post", "PhoneVerificationScope", "PhoneVerificationStatusResponse"),
        "/api/v1/phone-verification/cancel": ("post", "PhoneVerificationScope", "PhoneVerificationCancelResponse"),
        "/api/v1/phone-verification/update-phone": ("put", "UpdatePhoneRequest", "PhoneVerificationUpdateResponse"),
        "/api/v1/phone-verification/admin/send-code": ("post", "AdminSendCodeRequest", "AdminPhoneVerificationSendResponse"),
    }
    assert "get" not in paths["/api/v1/phone-verification/status"]
    assert "delete" not in paths["/api/v1/phone-verification/cancel"]
    for path, (method, request, response) in expected.items():
        operation = paths[path][method]
        assert operation.get("security"), path
        request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
        assert _ref_name(request_schema) == request
        assert not any(param.get("in") == "query" for param in operation.get("parameters", []))
        success = operation["responses"]["200"]
        assert _ref_name(success["content"]["application/json"]["schema"]) == response
        assert "Cache-Control" in success["headers"]
        assert {"401", "422", "500", "503"}.issubset(operation["responses"])

    components = schema["components"]["schemas"]
    for request in ("PhoneVerificationScope", "SendVerificationCodeRequest"):
        assert set(components[request]["properties"]["purpose"]["enum"]) == {"verification", "phone_change"}
    assert "admin endpoint" in components["SendVerificationCodeRequest"]["properties"]["custom_message"]["description"]
    assert "sessions_revoked" in components["PhoneVerificationUpdateResponse"]["required"]
    assert {"expires_in_seconds", "expires_in_minutes"}.issubset(components["PhoneVerificationSendResponse"]["required"])


def test_reset_phone_verification_publishes_token_and_failure_contract():
    schema = app.openapi()
    operation = schema["paths"]["/api/v1/password-reset/verify-phone"]["post"]
    request = operation["requestBody"]["content"]["application/json"]["schema"]
    assert _ref_name(request) == "PhoneVerificationRequest"
    success = operation["responses"]["200"]
    assert _ref_name(success["content"]["application/json"]["schema"]) == "PhoneResetVerificationResponse"
    assert "Cache-Control" in success["headers"]
    assert {"404", "422", "429", "503"}.issubset(operation["responses"])
    result = schema["components"]["schemas"]["PhoneResetVerificationResponse"]
    assert {"success", "message", "reset_token", "expires_in_hours"}.issubset(result["required"])


def test_verification_errors_document_actual_validation_and_rate_limit_shapes():
    schema = app.openapi()
    operation = schema["paths"]["/api/v1/phone-verification/verify-code"]["post"]
    validation = operation["responses"]["422"]["content"]["application/json"]["schema"]
    assert _ref_name(validation) == "PhoneVerificationValidationResponse"
    rate_limit = operation["responses"]["429"]["content"]["application/json"]["schema"]
    assert {_ref_name(item) for item in rate_limit["anyOf"]} == {
        "PhoneVerificationErrorResponse", "PhoneVerificationRateLimitResponse"
    }
