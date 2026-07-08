"""Backward-compatible shim for the openai_provider package.

Originally a 5450-LOC god file — now split into focused mixin modules
under :mod:`app.services.ai.openai_provider_pkg`. This module preserves
the historic import path ``app.services.ai.openai_provider`` so existing
callers (ai_manager.py, grok_provider.py) do not need to change.
"""
from __future__ import annotations

from app.services.ai.openai_provider_pkg import OpenAIProvider

__all__ = ["OpenAIProvider"]
