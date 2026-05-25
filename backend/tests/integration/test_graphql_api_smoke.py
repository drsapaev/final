from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.graphql.schema import graphql_admin_required, graphql_router, schema


def _app_with_graphql() -> FastAPI:
    app = FastAPI()
    app.include_router(graphql_router, prefix="/api")
    return app


def test_graphql_schema_mount_rejects_unauthenticated_request():
    app = _app_with_graphql()

    schema_text = schema.as_str()
    assert "type Query" in schema_text

    response = TestClient(app).post(
        "/api/graphql",
        json={"query": "query Smoke { __typename }"},
    )

    assert response.status_code == 401


def test_graphql_schema_mount_serves_typename_with_admin_dependency_override():
    app = _app_with_graphql()
    app.dependency_overrides[graphql_admin_required] = lambda: SimpleNamespace(
        id=1,
        role="Admin",
        is_active=True,
    )

    response = TestClient(app).post(
        "/api/graphql",
        json={"query": "query Smoke { __typename }"},
    )

    assert response.status_code == 200
    assert response.json() == {"data": {"__typename": "Query"}}
