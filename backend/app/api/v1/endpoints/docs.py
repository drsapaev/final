"""
API documentation helper endpoints.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


def _iter_operations(schema: dict[str, Any]):
    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() in _HTTP_METHODS:
                yield path, method.lower(), operation


def _existing_paths(
    published_paths: dict[str, Any],
    candidates: list[str],
    *,
    limit: int | None = None,
) -> list[str]:
    matches: list[str] = []
    for candidate in candidates:
        if candidate in published_paths and candidate not in matches:
            matches.append(candidate)
        if limit is not None and len(matches) >= limit:
            break
    return matches


def _top_tag_summaries(schema: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}

    for path, _method, operation in _iter_operations(schema):
        for tag in operation.get("tags") or ["untagged"]:
            bucket = buckets.setdefault(
                tag,
                {"tag": tag, "operations": 0, "sample_paths": []},
            )
            bucket["operations"] += 1
            if len(bucket["sample_paths"]) < 3 and path not in bucket["sample_paths"]:
                bucket["sample_paths"].append(path)

    ordered = sorted(
        buckets.values(),
        key=lambda item: (-int(item["operations"]), str(item["tag"])),
    )
    return ordered[:limit]


def _build_api_docs_html(path_count: int, operation_count: int) -> str:
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Clinic Manager API Docs Helper</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2937; }}
            h1, h2 {{ color: #111827; }}
            .lead {{ max-width: 920px; line-height: 1.6; }}
            .note {{ background: #eff6ff; border-left: 4px solid #2563eb; padding: 12px 16px; margin: 16px 0; }}
            .stats {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 20px 0; }}
            .stat {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 12px 16px; min-width: 180px; }}
            .stat strong {{ display: block; font-size: 1.6rem; color: #111827; }}
            code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; }}
            ul {{ line-height: 1.8; }}
            a {{ color: #2563eb; }}
        </style>
    </head>
    <body>
        <h1>Clinic Manager API Docs Helper</h1>
        <p class="lead">
            This page is a human-friendly landing page for the project API.
            The canonical contract still lives in the generated documentation:
            <code>/docs</code>, <code>/redoc</code>, and <code>/openapi.json</code>.
        </p>

        <div class="note">
            The older custom docs page drifted away from the live contract.
            This helper now points readers back to generated sources and only
            highlights selected live route families.
        </div>

        <div class="stats">
            <div class="stat">
                <strong>{path_count}</strong>
                <span>Published paths</span>
            </div>
            <div class="stat">
                <strong>{operation_count}</strong>
                <span>Published operations</span>
            </div>
        </div>

        <h2>Canonical generated docs</h2>
        <ul>
            <li><a href="/docs">Swagger UI</a></li>
            <li><a href="/redoc">ReDoc</a></li>
            <li><a href="/openapi.json">OpenAPI JSON</a></li>
        </ul>

        <h2>Custom helper endpoints</h2>
        <ul>
            <li><a href="/api/v1/docs/api-schema">/api/v1/docs/api-schema</a> - live schema mirror for the generated OpenAPI document</li>
            <li><a href="/api/v1/docs/endpoints-summary">/api/v1/docs/endpoints-summary</a> - live admin-only summary built from the current schema</li>
        </ul>

        <h2>Selected live route families</h2>
        <ul>
            <li><code>/api/v1/auth/login</code> and <code>/api/v1/auth/minimal-login</code> for Bearer-token login flows</li>
            <li><code>/api/v1/patients/</code> for patient registry routes</li>
            <li><code>/api/v1/visits/visits</code> for operational visit routes</li>
            <li><code>/api/v1/queue/join/start</code> and <code>/api/v1/queue/join/complete</code> for the modern queue join flow</li>
            <li><code>/api/v1/payments/init</code> and <code>/api/v1/payments/</code> for payment initiation and records</li>
            <li><code>/api/v1/messages/send</code> and <code>/api/v1/messages/send-voice</code> for messaging</li>
            <li><code>/api/v1/system/monitoring/health</code> for system monitoring</li>
        </ul>

        <h2>WebSocket families</h2>
        <p class="lead">
            WebSocket routes are runtime surfaces and are not represented in the
            OpenAPI schema. Current mounted families include
            <code>/ws/queue</code>, <code>/ws/chat</code>, <code>/ws/cashier</code>,
            <code>/api/v1/ws/notifications/connect</code>, and
            <code>/api/v1/ws-auth/*</code>.
        </p>
    </body>
    </html>
    """


@router.get("/api-docs", response_class=HTMLResponse)
async def get_api_docs(request: Request):
    """Return a small human-readable landing page for API docs."""
    schema = request.app.openapi()
    path_count = len(schema.get("paths", {}))
    operation_count = sum(1 for _ in _iter_operations(schema))
    return HTMLResponse(content=_build_api_docs_html(path_count, operation_count))


@router.get("/api-schema")
async def get_api_schema(request: Request):
    """Return the live generated OpenAPI schema used by /openapi.json."""
    return request.app.openapi()


@router.get("/endpoints-summary")
async def get_endpoints_summary(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Return a live summary of published endpoints for admin readers."""
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    schema = request.app.openapi()
    paths = schema.get("paths", {})
    operation_count = sum(1 for _ in _iter_operations(schema))

    route_families = [
        {
            "label": "Authentication",
            "sample_paths": _existing_paths(
                paths,
                [
                    "/api/v1/auth/login",
                    "/api/v1/auth/minimal-login",
                    "/api/v1/auth/me",
                ],
            ),
        },
        {
            "label": "Patients",
            "sample_paths": _existing_paths(
                paths,
                [
                    "/api/v1/patients/",
                    "/api/v1/patients/{patient_id}",
                    "/api/v1/patients/{patient_id}/appointments",
                ],
            ),
        },
        {
            "label": "Queue",
            "sample_paths": _existing_paths(
                paths,
                [
                    "/api/v1/queue/join/start",
                    "/api/v1/queue/join/complete",
                    "/api/v1/queue/status/{specialist_id}",
                ],
            ),
        },
        {
            "label": "Payments",
            "sample_paths": _existing_paths(
                paths,
                [
                    "/api/v1/payments/providers",
                    "/api/v1/payments/init",
                    "/api/v1/payments/",
                ],
            ),
        },
        {
            "label": "Monitoring",
            "sample_paths": _existing_paths(
                paths,
                [
                    "/api/v1/system/monitoring/health",
                    "/api/v1/system/monitoring/metrics/system",
                    "/api/v1/system/monitoring/alerts",
                ],
            ),
        },
        {
            "label": "Messaging",
            "sample_paths": _existing_paths(
                paths,
                [
                    "/api/v1/messages/send",
                    "/api/v1/messages/send-voice",
                    "/api/v1/messages/voice/{message_id}/stream",
                ],
            ),
        },
    ]

    return {
        "kind": "generated-openapi-summary",
        "canonical_sources": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_json": "/openapi.json",
        },
        "custom_docs_endpoints": {
            "api_docs": "/api/v1/docs/api-docs",
            "api_schema": "/api/v1/docs/api-schema",
            "endpoints_summary": "/api/v1/docs/endpoints-summary",
        },
        "path_count": len(paths),
        "operation_count": operation_count,
        "top_tags": _top_tag_summaries(schema),
        "sample_route_families": [
            family for family in route_families if family["sample_paths"]
        ],
        "websocket_families": [
            "/ws/queue",
            "/ws/chat",
            "/ws/cashier",
            "/api/v1/ws/notifications/connect",
            "/api/v1/ws-auth/*",
        ],
        "notes": [
            "Counts and samples are generated from the current OpenAPI schema, not from a hardcoded snapshot.",
            "Generated /docs and /openapi.json remain the canonical contract sources.",
            "WebSocket routes are listed separately because they are not represented in OpenAPI.",
        ],
    }
