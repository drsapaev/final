# W2D qr_queue_api_service cleanup repair

Date: 2026-03-11
Mode: bounded cleanup repair

## Why this repair was needed

`tests/unit/test_service_repository_boundary.py` still contained a stale
boundary gate for the removed duplicate file.

## What changed

Removed the stale test:

- `test_qr_queue_service_avoids_direct_session_calls`

## Why this was correct

The deleted file was no longer a mounted or owned runtime surface. Keeping a
boundary test for it would only preserve test drift.
