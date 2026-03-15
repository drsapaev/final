from fastapi.testclient import TestClient


def test_custom_api_schema_matches_generated_openapi(client: TestClient) -> None:
    canonical = client.get("/openapi.json")
    helper = client.get("/api/v1/docs/api-schema")

    assert canonical.status_code == 200
    assert helper.status_code == 200
    assert helper.json() == canonical.json()


def test_custom_api_docs_landing_page_points_to_canonical_docs(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/docs/api-docs")

    assert response.status_code == 200
    assert "/docs" in response.text
    assert "/redoc" in response.text
    assert "/openapi.json" in response.text
    assert "/api/v1/docs/api-schema" in response.text
    assert "/api/v1/docs/endpoints-summary" in response.text
    assert "wss://api.clinic.example.com/ws/" not in response.text
    assert "/api/v1/analytics/payment-providers" not in response.text


def test_endpoints_summary_uses_live_generated_counts(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    canonical = client.get("/openapi.json").json()
    response = client.get("/api/v1/docs/endpoints-summary", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    assert data["kind"] == "generated-openapi-summary"
    assert data["path_count"] == len(canonical["paths"])
    assert data["operation_count"] >= data["path_count"]
    assert data["canonical_sources"]["openapi_json"] == "/openapi.json"
    assert data["custom_docs_endpoints"]["api_schema"] == "/api/v1/docs/api-schema"
    assert any(item["tag"] == "admin" for item in data["top_tags"])


def test_endpoints_summary_is_admin_only(
    client: TestClient,
    registrar_auth_headers: dict[str, str],
) -> None:
    response = client.get(
        "/api/v1/docs/endpoints-summary",
        headers=registrar_auth_headers,
    )

    assert response.status_code == 403
