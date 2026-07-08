"""Backward-compatible shim for admin_departments package."""
from __future__ import annotations

from app.api.v1.endpoints.admin_departments import router  # noqa: F401

__all__ = ["router"]
