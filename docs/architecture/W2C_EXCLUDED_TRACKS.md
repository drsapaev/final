# Wave 2C Excluded Tracks

Date: 2026-03-09
Mode: analysis-first, docs-only

## Purpose

This document lists the work that is intentionally outside the completed Wave
2C main queue allocator track.

## 1. OnlineDay legacy island

- Why excluded:
  - separate department/day counter worldview
  - no bridge into `DailyQueue` / `OnlineQueueEntry`
  - explicit ownership decision: separate legacy island
- Current status:
  - live but isolated
- Future follow-up type:
  - legacy cleanup / deprecation preparation

Key docs:

- `docs/status/W2C_ONLINEDAY_TRACK_DECISION.md`
- `docs/architecture/W2C_ONLINEDAY_ISLAND_BOUNDARY.md`
- `docs/architecture/W2C_ONLINEDAY_CLEANUP_TRACK.md`

## 2. Force majeure exceptional-domain

- Why excluded:
  - intentional policy overrides
  - transfer/cancel/refund/deposit coupling
  - explicit domain decision: exceptional-domain with its own contract
- Current status:
  - live and isolated
- Future follow-up type:
  - exceptional-domain correction / follow-up track

Key docs:

- `docs/status/W2C_FORCE_MAJEURE_DOMAIN_DECISION.md`
- `docs/architecture/W2C_FORCE_MAJEURE_ISLAND_BOUNDARY.md`
- `docs/architecture/W2C_FORCE_MAJEURE_FOLLOWUP_TRACK.md`

## 3. Dead / duplicate queue cleanup

- Why excluded:
  - cleanup is not required to claim boundary-track completion
  - some mirrors are disabled, duplicate, or support-only
- Current status:
  - deferred intentionally
- Future follow-up type:
  - cleanup preparation / deprecation planning

Examples:

- disabled `online_queue` router
- duplicate service mirrors
- stale `crud/queue.py`
- unmounted queue-service mirrors

## 4. Deferred broader family follow-up

- Why excluded:
  - outside the mounted production allocator slices already migrated
- Current status:
  - deferred intentionally
- Future follow-up type:
  - case-by-case cleanup or domain-specific review

Examples:

- broader registrar orchestration beyond migrated mounted slices
- broader QR cleanup beyond the mounted full-update create branch

## Excluded-track verdict

These tracks are excluded by design, not by omission.

Their existence does not negate Wave 2C main-track completion.
