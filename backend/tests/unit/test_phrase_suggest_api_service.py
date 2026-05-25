from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.phrase_suggest_api_service import PhraseSuggestApiService


def _phrase_suggest_payload(doctor_id: int) -> dict:
    return {
        "field": "diagnosis",
        "currentText": "",
        "cursorPosition": 0,
        "doctorId": doctor_id,
        "maxSuggestions": 5,
    }


@pytest.mark.unit
class TestPhraseSuggestApiService:
    def test_get_phrase_stats_formats_output(self):
        stats_row = SimpleNamespace(field="diagnosis", count=2, total_usage=7)
        repository = SimpleNamespace(get_phrase_stats=lambda doctor_id: [stats_row])
        service = PhraseSuggestApiService(db=None, repository=repository)

        result = service.get_phrase_stats(doctor_id=1)

        assert result["doctorId"] == 1
        assert result["phrasesByField"]["diagnosis"]["uniquePhrases"] == 2
        assert result["phrasesByField"]["diagnosis"]["totalUsage"] == 7

    def test_get_telemetry_stats_builds_totals_and_top(self):
        totals = SimpleNamespace(total_shown=10, total_accepted=3)
        phrase = SimpleNamespace(
            phrase="Long phrase for testing",
            field="complaints",
            suggestions_accepted=3,
        )
        repository = SimpleNamespace(
            get_telemetry_totals=lambda doctor_id: totals,
            get_top_accepted_phrases=lambda doctor_id: [phrase],
        )
        service = PhraseSuggestApiService(db=None, repository=repository)

        result = service.get_telemetry_stats(doctor_id=2)

        assert result["doctorId"] == 2
        assert result["totalShown"] == 10
        assert result["totalAccepted"] == 3
        assert result["acceptanceRate"] == 30.0
        assert result["topAcceptedPhrases"][0]["field"] == "complaints"


@pytest.mark.integration
def test_phrase_suggest_requires_auth(client):
    response = client.post(
        "/api/v1/emr/phrase-suggest",
        json=_phrase_suggest_payload(doctor_id=1),
    )

    assert response.status_code == 401


@pytest.mark.integration
def test_phrase_suggest_allows_clinical_user(client, cardio_auth_headers, cardio_user):
    response = client.post(
        "/api/v1/emr/phrase-suggest",
        headers=cardio_auth_headers,
        json=_phrase_suggest_payload(doctor_id=cardio_user.id),
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "suggestions": [],
        "field": "diagnosis",
        "doctorId": cardio_user.id,
    }


@pytest.mark.integration
def test_batch_index_is_admin_only(client, cardio_auth_headers, auth_headers):
    doctor_response = client.post(
        "/api/v1/emr/batch-index",
        headers=cardio_auth_headers,
        json={"limit": 1, "offset": 0},
    )
    assert doctor_response.status_code == 403

    admin_response = client.post(
        "/api/v1/emr/batch-index",
        headers=auth_headers,
        json={"limit": 1, "offset": 0},
    )
    assert admin_response.status_code == 200, admin_response.text

