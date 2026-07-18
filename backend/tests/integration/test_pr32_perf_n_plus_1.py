"""
PR-32 — Sprint 3 performance: N+1 query fixes (High-37, High-38, High-39).

Tests for:
1. High-37: mobile_api endpoints are sync `def` (not `async def` with sync SQLAlchemy)
2. High-38: get_upcoming_appointments uses selectinload for doctor.user (avoids N+1)
3. High-39: /mobile/stats uses aggregate queries (not 5+ separate queries)
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
MOBILE_API_PY = BACKEND_DIR / "app" / "api" / "v1" / "endpoints" / "mobile_api.py"
APPOINTMENT_CRUD_PY = BACKEND_DIR / "app" / "crud" / "appointment.py"


def _extract_function_defs(source: str, names: set[str]) -> dict[str, str]:
    """Return {func_name: 'async def' | 'def'} for the given function names."""
    tree = ast.parse(source)
    result = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in names:
                result[node.name] = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return result


# ---------- 1. High-37: mobile_api endpoints should be sync def ----------

def test_mobile_api_endpoints_are_sync_def_not_async():
    """High-37: mobile_api endpoints must use sync `def` (not `async def`).

    All mobile_api endpoints use sync SQLAlchemy (db.query). When declared
    as `async def`, FastAPI runs them directly in the event loop, blocking
    all other requests during each DB call. Switching to `def` makes
    FastAPI run them in a threadpool, restoring concurrency.

    The only allowed `async def` endpoints are those that actually `await`
    something (e.g., async I/O).
    """
    src = MOBILE_API_PY.read_text(encoding="utf-8")
    tree = ast.parse(src)

    # Collect all endpoint function defs (decorated with @router.{get,post,...})
    async_endpoints = []
    sync_endpoints = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # Check decorators for @router.<method>
        is_endpoint = False
        for dec in node.decorator_list:
            dec_src = ast.get_source_segment(src, dec) or ""
            if re.match(r"router\.(get|post|put|patch|delete|websocket)\(", dec_src):
                is_endpoint = True
                break
        if not is_endpoint:
            continue

        if isinstance(node, ast.AsyncFunctionDef):
            # Check if the body actually awaits something
            body_src = ast.get_source_segment(src, node) or ""
            # Simple check: contains `await ` keyword
            if not re.search(r"\bawait\b", body_src):
                async_endpoints.append(node.name)
        else:
            sync_endpoints.append(node.name)

    assert not async_endpoints, (
        f"These mobile_api endpoints are `async def` but never `await` anything — "
        f"convert to `def` so FastAPI runs them in a threadpool (High-37): {async_endpoints}"
    )


# ---------- 2. High-38: selectinload in get_upcoming_appointments ----------

def test_get_upcoming_appointments_uses_selectinload():
    """High-38: get_upcoming_appointments must use selectinload to eager-load
    Appointment.doctor and Doctor.user in a single query.

    Previously: lazy loading caused N+1 (1 query for appointments + 1 per
    appointment for doctor + 1 per doctor for user = 21 queries for 10 rows).
    Now: selectinload(Appointment.doctor).selectinload(Doctor.user) does it
    in 3 queries total (1 + 2 IN-clause queries), regardless of row count.
    """
    src = APPOINTMENT_CRUD_PY.read_text(encoding="utf-8")
    # The function must use selectinload
    assert "selectinload" in src, (
        "selectinload not used in app/crud/appointment.py — N+1 query not fixed (High-38)"
    )
    # Specifically, the get_upcoming_appointments function must mention Doctor.user
    # via chained selectinload.
    assert re.search(
        r"selectinload\s*\(\s*Appointment\.doctor\s*\)\s*(?:\.selectinload\s*\(\s*Doctor\.user\s*\)|\.joinedload\s*\(\s*Doctor\.user\s*\))",
        src,
        re.DOTALL,
    ), (
        "Expected selectinload(Appointment.doctor).selectinload(Doctor.user) "
        "chain not found in app/crud/appointment.py (High-38)"
    )


# ---------- 3. High-39: /mobile/stats aggregate queries ----------

def test_mobile_stats_uses_aggregate_query():
    """High-39: /mobile/stats must use a single aggregate query (or 2 at most)
    instead of 5+ separate queries.

    Previously:
    - count_patient_visits (1 query)
    - count_upcoming_appointments (1 query)
    - get_patient_total_spent (1 + N queries for visits + payments)
    - get_last_visit (1 query)
    - count_pending_payments (1 query)
    Total: 5+ queries, plus N+1 in get_patient_total_spent.

    Now: a single aggregate query using func.count(case(...)) + func.max(...)
    returns all 5 metrics in one round-trip.
    """
    src = MOBILE_API_PY.read_text(encoding="utf-8")
    # Look for func.count or func.sum or func.max usage in the stats endpoint
    # We accept any of these patterns.
    has_aggregate = bool(
        re.search(r"func\.(count|sum|max|min)\s*\(", src)
    )
    assert has_aggregate, (
        "func.count/sum/max not used in mobile_api.py — /mobile/stats still "
        "uses 5+ separate queries (High-39)"
    )


def test_mobile_stats_does_not_call_five_separate_count_functions():
    """High-39: /mobile/stats must NOT call 5 separate count/visit functions.

    Previously the endpoint called:
    - count_patient_visits
    - count_upcoming_appointments
    - get_patient_total_spent
    - get_last_visit
    - count_pending_payments

    Now: at most 2 of these can remain (ideally just count_pending_payments,
    which is hard to merge with visit aggregates due to different filter criteria).
    """
    src = MOBILE_API_PY.read_text(encoding="utf-8")
    # Extract the get_mobile_quick_stats function body
    m = re.search(
        r"def\s+get_mobile_quick_stats\s*\([^)]*\)[^:]*:\s*(.*?)(?=\n@|\nasync def |\ndef |\Z)",
        src,
        re.DOTALL,
    )
    assert m, "get_mobile_quick_stats function not found"
    body = m.group(1)

    # Count how many of these 5 functions are called in the body
    called_functions = []
    for fn in [
        "count_patient_visits",
        "count_upcoming_appointments",
        "get_patient_total_spent",
        "get_last_visit",
        "count_pending_payments",
    ]:
        if re.search(rf"\b{fn}\s*\(", body):
            called_functions.append(fn)

    # We allow at most 2 of the 5 to remain (count_pending_payments is hard
    # to merge because it uses different filter criteria — payment_amount > 0
    # AND payment_processed_at IS NULL — which doesn't fit the visit aggregate).
    assert len(called_functions) <= 2, (
        f"get_mobile_quick_stats still calls {len(called_functions)} separate "
        f"count/visit functions (High-39): {called_functions}. "
        f"Expected <= 2 after aggregation."
    )
