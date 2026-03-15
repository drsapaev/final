# Wave 2D OnlineDay Support Cleanup Status

Date: 2026-03-09
Branch: `codex/post-w2c-onlineday-support-cleanup`
Mode: safe cleanup only
Verdict: `PARTIAL_SUCCESS`

## Removed

- `backend/app/services/online_queue_api_service.py`
- `backend/app/services/board_api_service.py`
- `backend/app/services/queues_api_service.py`

These files were confirmed as support-only mirrors:

- not mounted
- not imported by live runtime
- not required by route registration

## Follow-up result

Later bounded cleanup removed:

- `backend/app/services/appointments_api_service.py`

Why it became safe:

- mounted runtime still did not use it directly
- the only remaining dependency was a stale service-boundary test expectation
- that expectation was later corrected to match current runtime ownership

## Validation

- bootstrap import check for `app.api.v1.api` passed
- `pytest tests/test_openapi_contract.py -q` passed
- `pytest -q` passed after restoring `appointments_api_service.py`

## Cleanup interpretation

This slice safely removed the support-only mirrors that were truly detached from
runtime and test/bootstrap dependencies.

It also narrowed the remaining OnlineDay cleanup scope:

- live mounted legacy surfaces still need separate replacement prep
- the appointments support residue is no longer part of that scope
