"""Unit tests for app.services.wait_time_predictor.

Covers:
- Cache lifecycle (refresh, TTL, invalidation)
- Bucket lookup with 3-level fallback (bucket → specialty → global → default)
- Confidence levels based on sample size
- Queue length adjustment
- Percentile computation
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.services import wait_time_predictor


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset cache between tests."""
    wait_time_predictor._CACHE = {}
    wait_time_predictor._CACHE_TS = None
    yield
    wait_time_predictor._CACHE = {}
    wait_time_predictor._CACHE_TS = None


def _make_db_mock():
    """Mock DB session — predictor doesn't actually use it when cache is fresh."""
    return MagicMock()


class TestPercentile:
    def test_single_value(self):
        assert wait_time_predictor._percentile([10.0], 0.5) == 10.0

    def test_median_of_even_count(self):
        # [1, 2, 3, 4] → median = 2.5
        assert wait_time_predictor._percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5

    def test_p75(self):
        # 0..9 → p75 = 6.75
        vals = list(range(10))
        assert wait_time_predictor._percentile(vals, 0.75) == 6.75

    def test_empty_list_returns_zero(self):
        assert wait_time_predictor._percentile([], 0.5) == 0.0

    def test_p90(self):
        vals = list(range(10))
        assert wait_time_predictor._percentile(vals, 0.9) == 8.1


class TestCacheLifecycle:
    def test_invalidate_clears_cache(self):
        # Populate cache
        wait_time_predictor._CACHE = {"foo": "bar"}
        wait_time_predictor._CACHE_TS = datetime.utcnow()
        # Invalidate
        wait_time_predictor.invalidate_cache()
        assert wait_time_predictor._CACHE_TS is None
        # Cache dict is left intact but next call will refresh

    def test_ensure_cache_fresh_skips_when_within_ttl(self):
        # Set cache as fresh
        wait_time_predictor._CACHE = {"__global__": {"count": 100, "mean": 15.0, "median": 14.0, "p75": 20.0, "p90": 30.0}}
        wait_time_predictor._CACHE_TS = datetime.utcnow()
        db = _make_db_mock()
        # Should NOT execute any DB query
        wait_time_predictor._ensure_cache_fresh(db)
        db.execute.assert_not_called()


class TestPredictWaitMinutes:
    def setup_method(self):
        # Pre-populate cache with realistic test data
        wait_time_predictor._CACHE = {
            # Most-specific: cardiology Wed 10am, 50 samples
            ("cardiology", 3, 10): {"count": 50, "mean": 15.0, "median": 14.0, "p75": 20.0, "p90": 30.0},
            # Specialty aggregate: cardiology, 100 samples
            ("cardiology", -1, -1): {"count": 100, "mean": 18.0, "median": 17.0, "p75": 25.0, "p90": 40.0},
            # Global: 500 samples
            ("__global__", -1, -1): {"count": 500, "mean": 22.0, "median": 20.0, "p75": 30.0, "p90": 50.0},
        }
        wait_time_predictor._CACHE_TS = datetime.utcnow()

    def test_uses_bucket_when_available(self):
        # Wed 10am → bucket exists with 50 samples
        result = wait_time_predictor.predict_wait_minutes(
            _make_db_mock(),
            specialty="cardiology",
            target_dt=datetime(2026, 7, 8, 10, 0),  # Wednesday
            current_queue_length=0,
        )
        assert result["source"] == "bucket"
        assert result["confidence"] == "high"  # 50 samples
        assert result["predicted_minutes"] == 15.0
        assert result["sample_size"] == 50

    def test_falls_back_to_specialty_when_bucket_too_small(self):
        # Bucket has <10 samples → fall back to specialty
        wait_time_predictor._CACHE[("cardiology", 3, 11)] = {"count": 5, "mean": 25.0, "median": 24.0, "p75": 30.0, "p90": 45.0}
        result = wait_time_predictor.predict_wait_minutes(
            _make_db_mock(),
            specialty="cardiology",
            target_dt=datetime(2026, 7, 8, 11, 0),  # Wed 11am
            current_queue_length=0,
        )
        assert result["source"] == "specialty"
        assert result["predicted_minutes"] == 18.0  # specialty mean

    def test_falls_back_to_global_when_specialty_missing(self):
        # Unknown specialty → falls back to global
        result = wait_time_predictor.predict_wait_minutes(
            _make_db_mock(),
            specialty="unknown_specialty",
            target_dt=datetime(2026, 7, 8, 10, 0),
            current_queue_length=0,
        )
        assert result["source"] == "global"
        assert result["predicted_minutes"] == 22.0

    def test_returns_default_when_no_cache(self):
        wait_time_predictor._CACHE = {}
        result = wait_time_predictor.predict_wait_minutes(
            _make_db_mock(),
            specialty="cardiology",
            target_dt=datetime(2026, 7, 8, 10, 0),
            current_queue_length=0,
        )
        assert result["source"] == "default"
        assert result["confidence"] == "low"
        assert result["predicted_minutes"] == 15.0  # safe default
        assert "note" in result

    def test_queue_length_adjusts_prediction(self):
        # Bucket mean is 15.0, +5 min per person in queue (cap +60)
        result = wait_time_predictor.predict_wait_minutes(
            _make_db_mock(),
            specialty="cardiology",
            target_dt=datetime(2026, 7, 8, 10, 0),
            current_queue_length=3,
        )
        # 15 + 3*5 = 30
        assert result["predicted_minutes"] == 30.0
        assert result["queue_adjustment_minutes"] == 15

    def test_queue_length_caps_at_60(self):
        result = wait_time_predictor.predict_wait_minutes(
            _make_db_mock(),
            specialty="cardiology",
            target_dt=datetime(2026, 7, 8, 10, 0),
            current_queue_length=20,  # would be +100, capped at +60
        )
        assert result["queue_adjustment_minutes"] == 60
        assert result["predicted_minutes"] == 15.0 + 60

    def test_confidence_levels_by_sample_size(self):
        # 50 samples = high
        wait_time_predictor._CACHE[("derma", 3, 10)] = {"count": 50, "mean": 10.0, "median": 10.0, "p75": 12.0, "p90": 15.0}
        result = wait_time_predictor.predict_wait_minutes(
            _make_db_mock(),
            specialty="derma",
            target_dt=datetime(2026, 7, 8, 10, 0),
        )
        assert result["confidence"] == "high"

        # 25 samples = medium
        wait_time_predictor._CACHE[("derma", 3, 11)] = {"count": 25, "mean": 10.0, "median": 10.0, "p75": 12.0, "p90": 15.0}
        result = wait_time_predictor.predict_wait_minutes(
            _make_db_mock(),
            specialty="derma",
            target_dt=datetime(2026, 7, 8, 11, 0),
        )
        assert result["confidence"] == "medium"

        # 15 samples = low
        wait_time_predictor._CACHE[("derma", 3, 12)] = {"count": 15, "mean": 10.0, "median": 10.0, "p75": 12.0, "p90": 15.0}
        result = wait_time_predictor.predict_wait_minutes(
            _make_db_mock(),
            specialty="derma",
            target_dt=datetime(2026, 7, 8, 12, 0),
        )
        assert result["confidence"] == "low"

    def test_default_target_dt_is_now(self):
        # If target_dt is None, predictor uses datetime.utcnow()
        # We just verify it doesn't crash and produces a result
        result = wait_time_predictor.predict_wait_minutes(
            _make_db_mock(),
            specialty="cardiology",
            target_dt=None,
            current_queue_length=0,
        )
        assert "predicted_minutes" in result
        assert "confidence" in result
        assert "source" in result

    def test_bucket_field_in_response(self):
        result = wait_time_predictor.predict_wait_minutes(
            _make_db_mock(),
            specialty="cardiology",
            target_dt=datetime(2026, 7, 8, 10, 0),
            current_queue_length=0,
        )
        assert result["bucket"] == {"specialty": "cardiology", "dow": 3, "hour": 10}

    def test_bucket_none_when_fallback(self):
        result = wait_time_predictor.predict_wait_minutes(
            _make_db_mock(),
            specialty="unknown_specialty",
            target_dt=datetime(2026, 7, 8, 10, 0),
            current_queue_length=0,
        )
        # Source is global → bucket should be None
        assert result["source"] == "global"
        assert result["bucket"] is None

    def test_p75_and_p90_in_response(self):
        result = wait_time_predictor.predict_wait_minutes(
            _make_db_mock(),
            specialty="cardiology",
            target_dt=datetime(2026, 7, 8, 10, 0),
            current_queue_length=0,
        )
        assert result["p75_minutes"] == 20.0
        assert result["p90_minutes"] == 30.0

    def test_p75_and_p90_include_queue_adjustment(self):
        result = wait_time_predictor.predict_wait_minutes(
            _make_db_mock(),
            specialty="cardiology",
            target_dt=datetime(2026, 7, 8, 10, 0),
            current_queue_length=2,
        )
        # bucket p75=20, +2*5=10 → 30
        assert result["p75_minutes"] == 30.0
        assert result["p90_minutes"] == 40.0


class TestCacheRefresh:
    """Tests for _ensure_cache_fresh when cache is stale or empty."""

    def test_refresh_calls_db_when_cache_stale(self):
        # Set cache TS to 10 minutes ago (TTL is 5 min)
        from datetime import timedelta
        wait_time_predictor._CACHE_TS = datetime.utcnow() - timedelta(minutes=10)

        db = MagicMock()
        # Mock DB query result with no rows
        db.execute.return_value.all.return_value = []

        wait_time_predictor._ensure_cache_fresh(db)

        # DB execute should have been called
        db.execute.assert_called()
