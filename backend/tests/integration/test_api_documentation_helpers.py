from fastapi.testclient import TestClient


def test_documentation_endpoints_index_is_generated(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.get(
        "/api/v1/documentation/documentation/endpoints",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["kind"] == "generated-endpoint-index"
    assert data["canonical_sources"]["openapi_json"] == "/openapi.json"
    assert data["category_count"] > 0
    assert any(item["slug"] == "patients" for item in data["categories"])


def test_documentation_endpoints_category_filter_returns_live_group(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.get(
        "/api/v1/documentation/documentation/endpoints",
        params={"category": "patients"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "patients" in data
    assert data["patients"]["slug"] == "patients"
    assert data["patients"]["operation_count"] > 0


def test_documentation_examples_use_live_routes(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.get(
        "/api/v1/documentation/documentation/examples",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["kind"] == "curated-live-examples"
    assert (
        data["examples"]["visit_examples"]["create_visit"]["route"]
        == "/api/v1/visits/visits"
    )
    assert (
        data["examples"]["authentication_examples"]["minimal_login_json"]["route"]
        == "/api/v1/auth/minimal-login"
    )


def test_documentation_status_codes_are_generated_from_current_schema(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/documentation/documentation/status-codes")

    assert response.status_code == 200
    data = response.json()

    assert data["kind"] == "generated-status-code-guide"
    codes = {item["code"] for item in data["common_codes"]}
    assert "200" in codes
    assert "422" in codes


def test_documentation_authentication_uses_live_security_scheme(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/documentation/documentation/authentication")

    assert response.status_code == 200
    data = response.json()

    assert data["kind"] == "generated-auth-guide"
    assert "OAuth2PasswordBearer" in data["security_schemes"]
    assert "/api/v1/auth/minimal-login" in data["token_urls"]
    assert any(
        family["family"] == "auth" and family["path_count"] > 0
        for family in data["route_families"]
    )
