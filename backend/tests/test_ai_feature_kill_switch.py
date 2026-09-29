"""Behavioral proof for the AI feature-flag kill-switch (runbook Check 3).

The selected EMR route is intentionally unavailable and must stay fail-closed:
with the feature enabled (or missing), it returns ``ai_feature_unavailable``;
with the flag disabled, ``RequireAiFeature`` must run first and return
``feature_disabled``. The distinct responses prove the kill-switch intercepts
the route without invoking an AI provider or generating clinical content.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.models.feature_flags import FeatureFlag

GATED_ENDPOINT = "/api/v1/emr/ai-enhanced/generate-smart-template?specialty=cardiology"
FLAG_KEY = "ai_smart_template"


def _set_flag(db: Session, *, enabled: bool | None) -> None:
    """enabled=True/False sets the row, None removes it (fail-open state)."""
    db.query(FeatureFlag).filter(FeatureFlag.key == FLAG_KEY).delete()
    if enabled is not None:
        db.add(FeatureFlag(key=FLAG_KEY, name="AI Integration", enabled=enabled))
    db.commit()


@pytest.fixture(autouse=True)
def clean_flag(db_session):
    yield
    _set_flag(db_session, enabled=None)


def _response_error(response) -> str | None:
    """Extract the structured error returned by the gate or route."""
    detail = response.json().get("detail")
    return detail.get("error") if isinstance(detail, dict) else None


def test_disabled_flag_returns_503(client, auth_headers, db_session):
    _set_flag(db_session, enabled=False)

    response = client.post(GATED_ENDPOINT, json={}, headers=auth_headers)

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["error"] == "feature_disabled"
    assert detail["flag"] == FLAG_KEY
    assert "disabled by the administrator" in detail["message"]


def test_enabled_flag_reaches_intentionally_unavailable_route(
    client, auth_headers, db_session
):
    _set_flag(db_session, enabled=True)
    response = client.post(GATED_ENDPOINT, json={}, headers=auth_headers)

    assert response.status_code == 503
    assert _response_error(response) == "ai_feature_unavailable"


def test_missing_flag_fails_open(client, auth_headers, db_session):
    _set_flag(db_session, enabled=None)

    response = client.post(GATED_ENDPOINT, json={}, headers=auth_headers)

    assert response.status_code == 503
    assert _response_error(response) == "ai_feature_unavailable"


def test_runbook_check_uses_the_same_endpoint_and_distinguishes_503_reasons():
    repo_root = Path(__file__).resolve().parents[2]
    runbook = (repo_root / "docs/runbooks/STAGING_VALIDATION.md").read_text(
        encoding="utf-8"
    )
    check3 = runbook.split("## Check 3 — AI feature flags kill-switch", 1)[1].split(
        "## Check 4 — AI safety contract", 1
    )[0]

    assert GATED_ENDPOINT in check3
    assert "ai_feature_unavailable" in check3
    assert "feature_disabled" in check3
    assert FLAG_KEY in check3
