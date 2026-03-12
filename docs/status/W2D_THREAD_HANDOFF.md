# W2D Thread Handoff

Purpose:
- canonical handoff for continuing the long Post-W2C legacy/deprecation track in a new chat
- reduce repeated context compression overhead

Current branch:
- `codex/post-w2c-next-legacy-slice-review`

Current repo state:
- worktree is dirty by design
- do not reset or clean unrelated changes
- continue with review-first bounded slices only

## Stable Checkpoints

Completed / stabilized:
- Wave 2C main queue allocator architecture track is complete
- OnlineDay isolated as legacy island
- `force_majeure` isolated as exceptional-domain
- `queues.stats` has a partial SSOT-backed replacement
- new board-display endpoint exists
- `DisplayBoardUnified` is mostly off legacy `/api/v1/board/state`
- `postgres_pilot` marker exists
- dedicated CI job for `postgres_pilot` exists in `.github/workflows/ci-cd-unified.yml`
- SQLite default CI/test path remains intact

Postgres alignment status:
- `postgres_pilot` is operationally ready
- shared marker lane is green in SQLite and Postgres
- several real drifts were already fixed narrowly
- current posture: keep SQLite as default baseline, use `postgres_pilot` as guardrail

## Blocked Tails

Do not start these without a fresh review/decision:
- board semantics:
  - `is_paused`
  - `is_closed`
  - blocker: product semantics / ownership
- `open_day` / `close_day`
  - blocker: possible external/manual operational usage
- `next_ticket`
  - status: `DEPRECATE_LATER`
  - blocker: unresolved external/manual usage risk

## Actionable Track We Re-entered

Chosen re-entry track:
- `NEXT_TRACK_ONLINEDAY_DEPRECATION_CONTINUATION`

What we already did in this track:
- marked `/api/v1/appointments/stats` as deprecated in OpenAPI
- marked `/api/v1/appointments/qrcode` as deprecated in OpenAPI
- marked legacy `/api/v1/board/state` as deprecated in OpenAPI
- marked `queues.stats` compatibility fields `is_open` and `start_number` as deprecated
- reviewed board fallback and confirmed it is now mostly compatibility/rollback, not active migration work

## Duplicate / Unmounted Residue Cleanup Already Done

Service-side mirrors already removed:
- `backend/app/services/appointments_api_service.py`
- `backend/app/services/visit_confirmation_api_service.py`
- `backend/app/services/online_queue_legacy_api_service.py`
- `backend/app/services/online_queue_new_api_service.py`
- `backend/app/services/registrar_batch_api_service.py`
- `backend/app/services/registrar_wizard_api_service.py`
- `backend/app/services/registrar_integration_api_service.py`
- `backend/app/services/queue_batch_service.py`
- `backend/app/services/print_api_api_service.py`
- `backend/app/services/print_templates_api_service.py`
- `backend/app/services/qr_queue_api_service.py`
- `backend/app/services/api_documentation_api_service.py`
- `backend/app/services/docs_api_service.py`
- `backend/app/services/health_api_service.py`
- `backend/app/services/monitoring_api_service.py`

Endpoint-side dead artifacts already removed:
- `backend/app/api/v1/endpoints/online_queue.py`
- `backend/app/api/v1/endpoints/online_queue_legacy.py`
- `backend/app/api/v1/endpoints/monitoring.py`

Other cleanup already done:
- removed stale `backend/tests/unit/test_queue_batch_service.py`
- updated `backend/tests/unit/test_service_repository_boundary.py` where stale mirror checks remained
- corrected `docs/API_REFERENCE.md` so monitoring docs now point to mounted `/system/monitoring/*`, not dead `/admin/monitoring/*`

## Current Testing Signal

Last verified checks:
- `cd C:\final\backend && pytest tests/test_openapi_contract.py -q` -> `14 passed`
- `cd C:\final\backend && pytest -q` -> `782 passed, 3 skipped`

Use these as the default verification pair for bounded cleanup/deprecation slices unless a narrower test is more appropriate.

## Working Rules For Continuation

Continue with:
- review-first bounded slices
- one low-risk candidate at a time
- no runtime behavior changes unless the slice explicitly targets a narrow verified drift
- no broad refactors
- no touching blocked tails above

When cleaning residue:
- verify mounted owner
- verify no live source imports
- verify no live frontend/runtime dependency
- update stale docs if the cleanup removes a falsely documented surface

Before edits:
- send a short progress update
- explain the current candidate and why it is safe

After edits:
- run OpenAPI contract tests
- run full backend suite if the cleanup could affect imports or registration

## Best Next Slice

Recommended next execution unit:
- another review-first dead endpoint / duplicate residue slice

Why this is still the best next move:
- blocked semantic tails remain blocked
- high-value architecture work is already stabilized
- easy-but-real residue cleanup still exists, but each candidate now needs explicit import/runtime verification

Suggested candidate pattern:
1. inspect one candidate
2. prove mounted vs unmounted status
3. remove only if clearly dead
4. run:
   - `pytest tests/test_openapi_contract.py -q`
   - `pytest -q`

## How To Start A New Chat

Use a prompt like:

`Continue from C:/final/docs/status/W2D_THREAD_HANDOFF.md on branch codex/post-w2c-next-legacy-slice-review. Do the next bounded review-first legacy cleanup slice.`

This new chat will not automatically inherit the old conversation, but it will have access to:
- the same repository
- the same branch
- this handoff file
