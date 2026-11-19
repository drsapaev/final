"""Fail-closed discovery without a shared ceremony store."""

import pytest

from app.core.config import settings
from app.services import webauthn_service as ws


def test_discoverable_requires_shared_store(monkeypatch):
    monkeypatch.setattr(settings, "TESTING", True)
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://clinic.example")
    with pytest.raises(ws.WebAuthnStoreUnavailable):
        ws.begin_discoverable_authentication("synthetic-client")
