"""NURSE-V2 N2-2 — audit resource identity for ACCESS_DENIED rows (unit).

Codex post-settle P2 (PR #3333): the settle-2 denial audit derived the
resource identity with a positional parser (``path_parts[2]`` /
``path_parts[3]``), which assumes the flat ``/api/v1/{resource}/{id}``
shape. The control plane lives one scope deeper —
``/api/v1/admin/nurse-workplace-assignments/{assignment_id}/deactivate``
— so denials were labeled ``resource_type="admin"`` (the scope segment)
with ``resource_id=NULL`` and never surfaced in
``CRUDUserAuditLog.get_by_resource()`` history of the assignment the
stale token tried to reach; the id survived only inside the free-form
description.

These pins exercise ``_audit_resource_identity()`` directly (fabricated
scope dicts, no app/DB): the route-template anchor must attribute
admin-scoped item/collection routes to ``nurse_workplace_assignments``
(the snake_case vocabulary the SUCCESS-path ledger rows already use, so
denials and mutations join ONE resource history), must keep trailing
action segments (``/deactivate``) and scope segments (``admin``) out of
the identity, and must degrade to the legacy positional extraction when
route metadata is absent.
"""

from __future__ import annotations

from types import SimpleNamespace

from starlette.requests import Request

from app.core.security import _audit_resource_identity

_CONTROL_PLANE_ITEM = (
    "/api/v1/admin/nurse-workplace-assignments/{assignment_id}/deactivate"
)
_CONTROL_PLANE_COLLECTION = "/api/v1/admin/nurse-workplace-assignments"


def _request(
    path_format: str | None,
    path_params: dict[str, str] | None,
    path: str,
) -> Request:
    scope: dict = {
        "type": "http",
        "method": "POST",
        "path": path,
        # request.url (legacy fallback branch) builds from these:
        "headers": [],
        "query_string": b"",
        "scheme": "http",
    }
    if path_format is not None:
        scope["route"] = SimpleNamespace(path_format=path_format)
    if path_params is not None:
        scope["path_params"] = path_params
    return Request(scope)


def test_control_plane_item_route_names_the_assignment_resource() -> None:
    """The P2 case: a deactivate denial -> (nurse_workplace_assignments, 123)."""
    request = _request(
        _CONTROL_PLANE_ITEM,
        {"assignment_id": "123"},
        "/api/v1/admin/nurse-workplace-assignments/123/deactivate",
    )
    assert _audit_resource_identity(request) == ("nurse_workplace_assignments", 123)


def test_control_plane_get_item_route_keeps_the_identity() -> None:
    """The read side of the control plane attributes identically."""
    request = _request(
        "/api/v1/admin/nurse-workplace-assignments/{assignment_id}",
        {"assignment_id": "7"},
        "/api/v1/admin/nurse-workplace-assignments/7",
    )
    assert _audit_resource_identity(request) == ("nurse_workplace_assignments", 7)


def test_control_plane_collection_route_names_resource_without_row() -> None:
    """A create/list denial has no row to point at — type only, id=None."""
    request = _request(
        _CONTROL_PLANE_COLLECTION,
        {},
        "/api/v1/admin/nurse-workplace-assignments",
    )
    assert _audit_resource_identity(request) == ("nurse_workplace_assignments", None)


def test_flat_route_keeps_the_identity() -> None:
    """Non-admin routes keep the flat /api/v1/{resource}/{id} semantics."""
    request = _request("/api/v1/users/{user_id}", {"user_id": "5"}, "/api/v1/users/5")
    assert _audit_resource_identity(request) == ("users", 5)


def test_non_digit_param_yields_type_without_row_id() -> None:
    """A non-digit param cannot name a row — but the resource type stays."""
    request = _request(
        _CONTROL_PLANE_ITEM,
        {"assignment_id": "abc"},
        "/api/v1/admin/nurse-workplace-assignments/abc/deactivate",
    )
    assert _audit_resource_identity(request) == ("nurse_workplace_assignments", None)


def test_missing_route_metadata_falls_back_to_legacy_positional() -> None:
    """No route in scope (fabricated Request) -> documented degradation.

    The legacy positional fallback stays correct for the flat shape and
    keeps its historical (imperfect) answer for admin-scoped paths —
    pinned explicitly so the degradation contract stays honest.
    """
    flat = _request(None, None, "/api/v1/users/5")
    assert _audit_resource_identity(flat) == ("users", 5)

    admin_scoped = _request(
        None, None, "/api/v1/admin/nurse-workplace-assignments/1/deactivate"
    )
    assert _audit_resource_identity(admin_scoped) == ("admin", None)


def test_none_request_yields_no_identity() -> None:
    assert _audit_resource_identity(None) == (None, None)
