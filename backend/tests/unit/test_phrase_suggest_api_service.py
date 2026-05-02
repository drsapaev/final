from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.phrase_suggest_api_service import PhraseSuggestApiService


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

