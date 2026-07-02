# Wave 2C Registrar Batch Claim Model

Date: 2026-05-05
Mode: docs-only replacement for stale PR #78
Supersedes: old stacked PR #78 documentation assumptions that used `specialist_user_id` and `queue_tag=None`.
Depends on: merged replacement PR #264 current-main characterization.

## Current Mounted Contract

Registrar batch queue creation is currently claim-scoped by:

- `patient_id`
- resolved doctor profile id (`specialist_id` input maps to `doctors.id`)
- queue day
- the `DailyQueue` bucket resolved from the first service `queue_tag`

The mounted endpoint groups submitted services by resolved doctor. For a same-doctor multi-service batch, only one queue row is created for that doctor group, and the first service `queue_tag` selects the `DailyQueue` bucket.

This means the safe current claim key is:

```text
patient_id + doctor_id + queue_day + first_service_queue_tag_bucket
```

## Explicit Non-Contract

The old #78 wording is not current-main compatible when it says:

- `specialist_user_id` is the claim owner
- `DailyQueue` is created with `queue_tag=None`
- same specialist/day is sufficient without naming the service queue bucket

Those statements are stale after #264. The current source and characterization docs treat `specialist_id` as a doctor profile id and preserve first-service `queue_tag` bucket behavior.

## Target Policy Choice

Keep the registrar batch track doctor-profile scoped unless a separate product decision changes the mounted behavior.

Do not silently switch this flow to per-service queue rows. That would change patient queue cardinality, queue numbering, duplicate behavior, and downstream cashier/doctor expectations.

## Review Checklist

For any runtime PR touching this flow, reviewers should require proof for:

- `specialist_id` normalization to `doctors.id`
- same-doctor multi-service grouping
- first service `queue_tag` bucket selection
- duplicate lookup inside the resolved queue bucket
- no accidental fallback to `users.id` or `queue_tag=None`
