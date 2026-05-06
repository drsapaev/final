from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.graphql.schema import graphql_router, schema


def test_graphql_schema_mount_serves_typename_smoke():
    app = FastAPI()
    app.include_router(graphql_router, prefix="/api")

    schema_text = schema.as_str()
    assert "type Query" in schema_text

    response = TestClient(app).post(
        "/api/graphql",
        json={"query": "query Smoke { __typename }"},
    )

    assert response.status_code == 200
    assert response.json() == {"data": {"__typename": "Query"}}
