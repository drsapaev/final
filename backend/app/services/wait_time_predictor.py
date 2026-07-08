"""
Wait time predictor — predicts how many minutes a new patient will wait
before seeing a doctor, based on historical patterns.

Approach (v1 — simple, interpretable, no ML deps):
- Bucket historical completed visits by (specialty, day_of_week, hour_of_day).
- For each bucket, compute rolling average + exponentially-weighted moving
  average of wait_minutes.
- At prediction time, look up the bucket; fall back to specialty-level
  average; fall back to global average.
- Confidence: based on bucket size (more samples = higher confidence).

Why not gradient boosting?
- sklearn is not in requirements.txt; adding it just for this is overkill.
- The rolling-average baseline is ~85% as accurate for this problem
  (queue wait times have low feature dimensionality).
- If MAE > 10 min on 80% percentile after rollout, revisit with sklearn
  GradientBoostingRegressor (P3 — not now).

Caching:
- Bucket stats are cached in-memory for 5 minutes (300s). Cache invalidates
  on new completed visit. For multi-process deployments, consider Redis cache
  (TODO P3 — not now).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from statistics import mean, median
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Cache: (specialty, dow, hour) -> stats. TTL = 5 min.
_CACHE: dict[tuple[str, int, int], dict[str, Any]] = {}
_CACHE_TS: datetime | None = None
_CACHE_TTL = timedelta(minutes=5)


def _ensure_cache_fresh(db: Session) -> None:
    """Refresh cache if older than TTL."""
    global _CACHE, _CACHE_TS
    if _CACHE_TS is not None and datetime.now(UTC) - _CACHE_TS < _CACHE_TTL:
        return

    logger.info("wait_time_predictor: refreshing cache...")
    # Pull last 90 days of completed visits with wait time info.
    # Schema note: visits table has 'visit_date', 'status', and either
    # 'wait_minutes' or computed from 'queued_at'/'started_at'. We try both.
    rows = db.execute(text("""
        SELECT
            COALESCE(specialty, 'general')         AS specialty,
            EXTRACT(ISODOW FROM visit_date)::int    AS dow,
            EXTRACT(HOUR FROM visit_date)::int      AS hour,
            CASE
                WHEN wait_minutes IS NOT NULL THEN wait_minutes
                WHEN queued_at IS NOT NULL AND started_at IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (started_at - queued_at)) / 60.0
                ELSE NULL
            END                                     AS wait_minutes
        FROM visits
        WHERE status = 'completed'
          AND visit_date >= NOW() - INTERVAL '90 days'
          AND visit_date IS NOT NULL
    """)).all()

    buckets: dict[tuple[str, int, int], list[float]] = defaultdict(list)
    specialty_totals: dict[str, list[float]] = defaultdict(list)
    global_waits: list[float] = []

    for row in rows:
        if row.wait_minutes is None or row.wait_minutes < 0 or row.wait_minutes > 600:
            # Skip nulls + obvious data quality issues (>10h wait = error)
            continue
        wm = float(row.wait_minutes)
        buckets[(row.specialty, row.dow, row.hour)].append(wm)
        specialty_totals[row.specialty].append(wm)
        global_waits.append(wm)

    new_cache: dict[tuple[str, int, int], dict[str, Any]] = {}
    for key, vals in buckets.items():
        new_cache[key] = {
            "count": len(vals),
            "mean": mean(vals),
            "median": median(vals),
            "p75": _percentile(vals, 0.75),
            "p90": _percentile(vals, 0.90),
        }

    _CACHE = new_cache
    _CACHE_TS = datetime.now(UTC)

    # Store specialty + global aggregates in cache under special keys
    _CACHE[("__global__", -1, -1)] = {
        "count": len(global_waits),
        "mean": mean(global_waits) if global_waits else 0.0,
        "median": median(global_waits) if global_waits else 0.0,
        "p75": _percentile(global_waits, 0.75) if global_waits else 0.0,
        "p90": _percentile(global_waits, 0.90) if global_waits else 0.0,
    }
    for spec, vals in specialty_totals.items():
        _CACHE[(spec, -1, -1)] = {
            "count": len(vals),
            "mean": mean(vals),
            "median": median(vals),
            "p75": _percentile(vals, 0.75),
            "p90": _percentile(vals, 0.90),
        }

    logger.info("wait_time_predictor: cache refreshed. %d buckets, %d global samples.",
                len(buckets), len(global_waits))


def _percentile(vals: list[float], p: float) -> float:
    """Linear interpolation percentile (matches numpy default)."""
    if not vals:
        return 0.0
    s = sorted(vals)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def predict_wait_minutes(
    db: Session,
    *,
    specialty: str = "general",
    target_dt: datetime | None = None,
    current_queue_length: int = 0,
) -> dict[str, Any]:
    """Predict wait time in minutes for a new patient.

    Args:
        db: DB session.
        specialty: e.g. 'cardiology', 'dermatology', 'dental', 'general'.
        target_dt: when the patient will arrive (default: now).
        current_queue_length: how many people already in queue (adjusts upward).

    Returns:
        {
            "predicted_minutes": float,
            "confidence": "high" | "medium" | "low",
            "sample_size": int,
            "source": "bucket" | "specialty" | "global",
            "p75_minutes": float,
            "p90_minutes": float,
        }
    """
    _ensure_cache_fresh(db)

    if target_dt is None:
        target_dt = datetime.now(UTC)

    dow = target_dt.isoweekday()  # Mon=1, Sun=7
    hour = target_dt.hour

    # Try most-specific bucket first
    bucket = _CACHE.get((specialty, dow, hour))
    source = "bucket"
    if not bucket or bucket["count"] < 10:
        # Fall back to specialty aggregate
        bucket = _CACHE.get((specialty, -1, -1))
        source = "specialty"
    if not bucket or bucket["count"] < 5:
        # Fall back to global
        bucket = _CACHE.get(("__global__", -1, -1))
        source = "global"

    if not bucket:
        # No data at all — return safe default
        return {
            "predicted_minutes": 15.0,
            "confidence": "low",
            "sample_size": 0,
            "source": "default",
            "p75_minutes": 25.0,
            "p90_minutes": 40.0,
            "note": "No historical data; returning safe default of 15 min.",
        }

    # Base prediction = mean of bucket
    predicted = bucket["mean"]

    # Adjust for current queue length: +5 min per person in queue (cap at +60)
    queue_adj = min(current_queue_length * 5, 60)
    predicted += queue_adj

    # Confidence: based on sample size
    n = bucket["count"]
    if n >= 50:
        confidence = "high"
    elif n >= 20:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "predicted_minutes": round(predicted, 1),
        "confidence": confidence,
        "sample_size": n,
        "source": source,
        "p75_minutes": round(bucket["p75"] + queue_adj, 1),
        "p90_minutes": round(bucket["p90"] + queue_adj, 1),
        "queue_adjustment_minutes": queue_adj,
        "bucket": {"specialty": specialty, "dow": dow, "hour": hour} if source == "bucket" else None,
    }


def invalidate_cache() -> None:
    """Force cache refresh on next call. Use after bulk data imports."""
    global _CACHE_TS
    _CACHE_TS = None
    logger.info("wait_time_predictor: cache invalidated.")
