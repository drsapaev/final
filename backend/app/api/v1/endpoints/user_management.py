"""Backward-compatible shim for user_management package."""
from __future__ import annotations

from app.api.v1.endpoints.user_management import router  # noqa: F401

__all__ = ["router"]
