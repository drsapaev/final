"""Published contracts for password-reset credentials and activation limits."""

from fastapi.testclient import TestClient


def test_reset_validation_contract_has_header_and_deprecated_query(client: TestClient):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/password-reset/validate-token"]["get"]
    parameters = {(item["in"], item["name"]): item for item in operation["parameters"]}

    assert ("header", "X-Reset-Token") in parameters
    assert not parameters[("header", "X-Reset-Token")].get("required", False)
    legacy = parameters[("query", "token")]
    assert legacy["deprecated"] is True
    assert not legacy.get("required", False)
    assert {"200", "400", "404", "409", "410", "500", "503"} <= set(operation["responses"])
    assert "Cache-Control" in operation["responses"]["200"]["headers"]


def test_activation_and_setup_document_rate_limit_and_outage(client: TestClient):
    schema = client.get("/openapi.json").json()
    for path in ("/api/v1/activation/activate", "/api/v1/setup/initialize"):
        responses = schema["paths"][path]["post"]["responses"]
        for status in ("429", "503"):
            response_schema = responses[status]["content"]["application/json"]["schema"]
            assert "detail" in response_schema["required"]
            assert response_schema["properties"]["detail"]["type"] == "string"
        assert "Retry-After" in responses["429"]["headers"]
