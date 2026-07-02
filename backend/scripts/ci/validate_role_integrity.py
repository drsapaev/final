#!/usr/bin/env python3
"""
Deterministic role integrity checks for CI fallback paths.

This script validates:
1. Required RBAC-related API routes are present.
2. Core role definitions pass integrity validation.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from fastapi.routing import APIRoute

EXIT_OK = 0
EXIT_IMPORT_ERROR = 10
EXIT_MISSING_ROUTES = 20
EXIT_ROLE_VALIDATION_FAILED = 30
EXIT_UNEXPECTED_ERROR = 40

REQUIRED_ROUTES = {
    "/api/v1/auth/minimal-login",
    "/api/v1/admin/permissions/roles",
}


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def _add_backend_root_to_syspath() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    backend_root_str = str(backend_root)
    if backend_root_str not in sys.path:
        sys.path.insert(0, backend_root_str)


def _collect_routes(app) -> set[str]:
    return {route.path for route in app.routes if isinstance(route, APIRoute)}


def run() -> int:
    parser = argparse.ArgumentParser(description="Validate RBAC role integrity")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging",
    )
    args = parser.parse_args()

    _configure_logging(args.verbose)
    logger = logging.getLogger("role_integrity_check")
    logger.info("role.integrity.check.start")

    try:
        _add_backend_root_to_syspath()
        from app.core.role_validation import validate_critical_user_roles
        from app.main import app
    except Exception:
        logger.exception("role.integrity.check.import_error")
        return EXIT_IMPORT_ERROR

    try:
        routes = _collect_routes(app)
        missing = sorted(REQUIRED_ROUTES - routes)
        if missing:
            logger.error(
                "role.integrity.check.missing_routes missing=%s total_routes=%d",
                missing,
                len(routes),
            )
            return EXIT_MISSING_ROUTES

        if not validate_critical_user_roles():
            logger.error("role.integrity.check.role_validation_failed")
            return EXIT_ROLE_VALIDATION_FAILED

        logger.info(
            "role.integrity.check.success required_routes=%d total_routes=%d",
            len(REQUIRED_ROUTES),
            len(routes),
        )
        return EXIT_OK
    except Exception:
        logger.exception("role.integrity.check.unexpected_error")
        return EXIT_UNEXPECTED_ERROR


if __name__ == "__main__":
    raise SystemExit(run())
