# Wave 2C Registrar Batch Duplicate Contract

Date: 2026-05-05
Mode: docs-only replacement for stale PR #78

## Current Duplicate Key

The current registrar batch duplicate boundary should be read as:

```text
patient_id + doctor_id + queue_day + first_service_queue_tag_bucket
```

Where:

- `doctor_id` is the resolved `doctors.id` value accepted through `specialist_id`
- `queue_day` is the current `DailyQueue.day`
- `first_service_queue_tag_bucket` is the queue bucket selected from the first submitted service for that doctor group

## Active Statuses

The duplicate policy must be explicit about which existing entries block a new batch queue entry.

Current characterization around the batch family treats active queue rows as the relevant guard. Reviewers should verify the runtime implementation and tests before changing this list. The intended active set for future hardening is:

- `waiting`
- `called`
- `in_service`
- `diagnostics`

If current mounted code only guards a narrower subset in a specific endpoint path, document that as a runtime conflict instead of pretending the policy is already fully enforced.

## Compatibility Rules

A compatibility-safe change must not:

- compare doctor profile ids against `users.id`
- ignore the service queue bucket selected by the first service
- create duplicate queue rows for the same doctor group without an explicit product decision
- hide ambiguous duplicate behavior behind a generic success response

## Required Proof In Future Runtime PRs

A runtime PR touching this area should include at least:

- positive proof: new batch creates one row for a doctor group
- duplicate proof: same patient/doctor/day/bucket is rejected or reused according to the selected policy
- negative proof: a different queue bucket is handled deliberately, not accidentally
- compatibility proof: old `specialist_user_id` wording is not reintroduced
