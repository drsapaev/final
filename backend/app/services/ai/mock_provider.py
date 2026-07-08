"""Backward-compatible shim for the mock_provider package.

Originally a 4669-LOC god file — now split into focused mixin modules
under :mod:`app.services.ai.mock_provider_pkg`.
"""
from __future__ import annotations

from app.services.ai.mock_provider_pkg import MockProvider

__all__ = ["MockProvider"]
