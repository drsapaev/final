# W2D Duplicate Residue Review

Date: 2026-03-11
Mode: docs-only review

## Purpose

After several successful support-only cleanup slices, the next question was
whether another low-risk duplicate/unmounted residue candidate still existed.

## Checked candidates

### `backend/app/crud/queue.py`

Verdict: **not a cleanup candidate**

Why:

- it has multiple live source imports
- it is still referenced by mounted endpoints such as
  `mobile_api_extended.py`
- it is therefore not dead residue anymore, regardless of older cleanup docs

### `backend/app/services/patient_appointments_api_service.py`

Verdict: **not a cleanup candidate**

Why:

- it is directly imported by mounted
  `backend/app/api/v1/endpoints/patient_appointments.py`
- it has dedicated unit tests

### `backend/app/services/registrar_batch_api_service.py`

Verdict: **not a low-risk cleanup candidate**

Why:

- it is not imported as a service by other source files
- but it contains a router-like mounted contract surface in its own right
- older architecture docs already classify it as part of the remaining
  registrar duplicate/unmounted family, not as a trivial safe deletion

That makes it a review/migration/retirement candidate, not a support-only
cleanup candidate.

## Current review conclusion

The obvious low-risk duplicate/unmounted cleanup pool is now much smaller than
before.

Recently successful removals:

- `appointments_api_service.py`
- `visit_confirmation_api_service.py`
- `online_queue_legacy_api_service.py`

What remains is increasingly mixed with:

- mounted contracts
- duplicate registrar surfaces
- cleanup that needs a separate review before deletion

## Practical implication

The cleanup track can still continue, but it should no longer assume that every
leftover duplicate-like file is safe to delete immediately.

From this point onward, each candidate needs explicit review first.
