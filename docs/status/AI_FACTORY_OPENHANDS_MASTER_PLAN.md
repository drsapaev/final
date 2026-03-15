# AI Factory + OpenHands Master Plan

Updated: 2026-03-14
Status: current execution source of truth

## Why this file exists

This file replaces the old early-phase master snapshot from 2026-03-06 as the
single current plan/status document for the long AI Factory + OpenHands track.

Use this document first when re-entering work after a pause.

Related historical docs still exist, but they should now be treated as
supporting records, not as the primary execution source:

- `docs/status/W2D_STATUS_NAVIGATION_INDEX.md`
- `docs/status/OPENHANDS_TASK_BACKLOG.md`
- `docs/status/OPENHANDS_FIRST_10_TASKS.md`
- `docs/status/AI_FACTORY_OPENHANDS_PRECHECK.md`
- `docs/status/W2D_THREAD_HANDOFF.md`

## Current Program Phase

The project is no longer in the early setup/stabilization phase.

It has moved through:

1. AI Factory + OpenHands setup
2. Wave 1 stabilization and truth-finding
3. Wave 2C main queue architecture work
4. Postgres alignment / pilot operationalization

It is now in:

`legacy reduction + deprecation continuation + bounded cleanup`

## What is already completed or strongly stabilized

### Infrastructure / execution model

- AI Factory installed and actively used
- OpenHands-oriented contract workflow established
- custom skills added and usable in this repo
- PR-first bounded execution model established
- `postgres_pilot` marker exists
- dedicated CI guardrail job for `postgres_pilot` exists
- default SQLite-oriented CI/test lane remains intact

### Main architecture outcomes

- Wave 2C main queue allocator architecture track is complete
- OnlineDay isolated as a legacy island
- `force_majeure` isolated as an exceptional-domain
- `queues.stats` has a partial SSOT-backed replacement with compatibility
  fallback
- new board-display endpoint exists
- `DisplayBoardUnified` is mostly off legacy `/api/v1/board/state`
- board metadata migration is mostly complete

### Postgres alignment outcome

- `postgres_pilot` is operationally ready
- pilot is green in SQLite and Postgres
- real schema drift, harness drift, and datetime drift were found and fixed
  narrowly
- current conclusion: full immediate migration of the whole test stack to
  Postgres is not required right now

## Major tracks and current status

| Track | Status | Notes |
|---|---|---|
| AI Factory / OpenHands setup | done | No longer a blocker |
| Wave 1 stabilization | done / archived | Truth matrix, docs truth, security baseline completed |
| Main queue architecture (Wave 2C core) | done | Core allocator track complete |
| Postgres alignment | done / guarded | `postgres_pilot` CI guardrail in place |
| OnlineDay deprecation continuation | active, partially blocked | Still a live legacy track, but no longer the immediate next slice |
| Residue cleanup | done outside protected zones | Non-protected cleanup lane is effectively exhausted |
| Protected residue gates | done / exhausted | Duplicate cleanup and the last active 2FA parity gate are resolved; cashier remains a separate architecture review surface outside cleanup |
| Docs consolidation | active | This is now the safest next low-risk track after residue resolution; late protected pointer docs are normalized and a status landing page now exists |

## Current blocked tails

These are not the best next engineering slices right now.

### Product-semantics blocked

- board flags:
  - `is_paused`
  - `is_closed`

Reason:
- ownership/meaning is still product-level, not just engineering

### Ops / external-usage blocked

- `open_day`
- `close_day`

Reason:
- possible manual/external operational usage still exists

### Defer-later legacy tail

- `next_ticket`

Current verdict:
- `DEPRECATE_LATER`

Reason:
- legacy ticket issuance route with unresolved external/manual usage risk

## Current actionable work

### Highest-value actionable track

`NEXT_TRACK_DOCS_CONSOLIDATION_AFTER_RESIDUE_RESOLUTION`

Why:
- non-protected cleanup and mixed-risk follow-up have already been exhausted or
  resolved
- the protected payment/auth/queue/EMR duplicate lanes are now resolved
- the last active `/api/v1/2fa/devices*` parity gate has also been resolved
  without changing runtime ownership
- the next honest entry point is now docs/status consolidation while keeping
  cashier out of cleanup
- the first docs pass in that track has already normalized the late protected
  `NEXT_EXECUTION_UNIT_AFTER_*` chain so it no longer competes with the live
  SSOT
- the second docs pass in that track has now added
  `docs/status/W2D_STATUS_NAVIGATION_INDEX.md` as a direct landing page for
  W2D re-entry
- the third docs pass in that track has now normalized the older re-entry docs
  so they point back to the live status landing page and canonical SSOT
- the first broader docs-vs-code pass outside the status stack has now started
  on `docs/API_REFERENCE.md`, correcting the verified `Notifications` and
  `Settings` drift and reframing that file as curated documentation
- the second bounded docs-vs-code pass in that same track has now corrected
  the verified `Authentication` and `Users` drift in `docs/API_REFERENCE.md`,
  including the split `/auth/*` versus `/authentication/*` surface and the live
  `/users/me/preferences` plus `/users/users*` ownership model
- the third bounded docs-vs-code pass in that same track has now corrected the
  verified `Queue` drift in `docs/API_REFERENCE.md`, reframing that section
  around the live session-based `/queue/join/*` flow, public position/status
  surfaces, and explicit `/queue/legacy/*` compatibility routes
- the fourth bounded docs-vs-code pass in that same track has now corrected
  the protected `Payments` drift in `docs/API_REFERENCE.md`, separating public
  provider/webhook routes, provider-init flow, cashier creation, and
  reconciliation surfaces without touching payment runtime behavior
- the fifth bounded docs-vs-code pass in that same track has now corrected the
  `Analytics` drift in `docs/API_REFERENCE.md`, replacing removed top-level
  analytics routes with the live dashboard surface and adjacent analytics route
  families without trying to turn the file into a generated spec
- the sixth bounded docs-vs-code pass in that same track has now corrected the
  `Departments` and `Services` drift in `docs/API_REFERENCE.md`, removing
  stale department CRUD claims and reframing services around the live
  catalog/category/helper route families without touching runtime behavior
- the seventh bounded docs-vs-code pass in that same track has now corrected
  the stale `Doctors` narrative in `docs/API_REFERENCE.md` and added a curated
  operational `Appointments` section that reflects the live split
  `/doctor-info/*`, `/doctor/*`, `/admin/doctors*`, and `/appointments*`
  surface without changing runtime behavior
- the eighth bounded docs-vs-code pass in that same track has now corrected
  the patient portal route-prefix drift and reframed `Visits` in
  `docs/API_REFERENCE.md` around the live `/patients/*`, `/patients/results`,
  and `/visits/visits*` surface without touching runtime behavior
- the ninth bounded docs-vs-code pass in that same track has now corrected the
  broader `Patients` registry summary and added a curated `Schedule` section in
  `docs/API_REFERENCE.md`, aligning patient search/filter notes and the live
  `/schedule*` helper surface without touching runtime behavior
- the tenth bounded docs-vs-code pass in that same track has now corrected the
  footer-level `Health` and `Authentication Header` sections in
  `docs/API_REFERENCE.md`, aligning them to the live `/health` plus `/status`
  owner shape and the published `OAuth2PasswordBearer` security scheme without
  touching runtime behavior
- the eleventh bounded docs-vs-code pass in that same track has now corrected
  the generic `HTTP Status Codes` and `Roles & Permissions` footer sections in
  `docs/API_REFERENCE.md`, downgrading them from overconfident tables to
  current response-pattern and RBAC-glossary guidance without touching runtime
  behavior
- the twelfth bounded docs-vs-code pass in that same track has now corrected
  the stale `New Modules` and `Links` footer sections in `docs/API_REFERENCE.md`,
  replacing non-published ECG/odontogram/audio claims and a fake websocket host
  with current curated route-family and navigation guidance without touching
  runtime behavior
- the thirteenth bounded docs-vs-code pass in that same track has now moved
  from Markdown into the mounted custom `/api/v1/docs/*` helper endpoints,
  replacing a stale HTML brochure, fake mini-schema, and hardcoded endpoint
  counts with live generated pointers and summary data without changing the
  canonical generated docs setup
- the fourteenth bounded docs-vs-code pass in that same track has now
  corrected the neighboring mounted `/api/v1/documentation/*` helper router,
  replacing stale route narratives, examples, auth notes, and status-code prose
  with generated summaries and current live-helper guidance
- the fifteenth bounded docs-vs-code pass in that same track has now reframed
  `backend/PRODUCTION_READINESS_REPORT.md` as a historical readiness snapshot,
  replacing a misleading current-looking `PRODUCTION READY` verdict with
  snapshot framing, SSOT pointers, and the current verification baseline
- the sixteenth bounded docs-vs-code pass in that same track has now reframed
  `backend/SETUP_PRODUCTION.md` and `backend/PRODUCTION_SETUP_SUMMARY.md` into
  curated setup docs with explicit compose/env, monitoring, gunicorn, and
  legacy-readiness-script caveats instead of drop-in production claims
- the seventeenth bounded docs-vs-code pass in that same track has now
  reframed `backend/PRODUCTION_READINESS_CHECKLIST.md` into an archived
  FK/database-integrity checklist with explicit PostgreSQL/SQLite and
  Windows-console caveats for the legacy readiness helper scripts instead of a
  whole-system production verdict
- the eighteenth bounded docs-vs-code pass in that same track has now
  normalized `ops/README.md` and `ops/.env.example` into compose-oriented docs
  with explicit PostgreSQL-first, env-layer, admin-bootstrap, and legacy
  `AUTH_SECRET` caveats instead of a clean turnkey deployment story
- the nineteenth bounded docs-vs-code pass in that same track has now
  normalized `backend/env_setup_guide.md` into a dev-first env entry guide
  that points back to the live templates and current setup docs instead of
  duplicating stale env snippets and dead links
- the twentieth bounded docs-vs-code pass in that same track has now
  normalized `backend/.env.example` itself, removing stale split-Postgres
  comments and aligning the template with current `SECRET_KEY`, logging,
  frontend URL, backup, and optional FCM guidance
- the twenty-first bounded docs-vs-code/support-file pass in that same track
  has now corrected `ops/docker-compose.yml` path wiring, removing the
  obsolete compose `version` stanza and aligning build contexts, bind mounts,
  and `env_file` to the actual repo layout under `ops/` without changing the
  behavior-bearing auth/dev defaults in that file
- the twenty-second bounded docs-vs-code/support-file pass in that same track
  has now corrected the fallback-path drift in `ops/backend.entrypoint.sh`,
  aligning its SQLite default with the current backend env/config story while
  deliberately leaving `create_all` and auto-admin behavior as separate
  startup-semantics review tails
- the twenty-third bounded docs-vs-code/status pass in that same track has now
  opened the explicit startup-semantics plan gate for
  `ops/backend.entrypoint.sh`, classifying metadata schema bootstrap and
  default auto-admin behavior as review-required policy tails and tightening
  neighboring ops/production docs so those behaviors are no longer implicit
- the twenty-fourth bounded startup-hardening pass in that same track has now
  executed the operator-first decision for `ops/backend.entrypoint.sh`,
  removing implicit `create_all` startup behavior, making `ENSURE_ADMIN`
  explicit opt-in, and aligning root/ops/production docs plus env examples to
  the new startup contract
- the twenty-fifth bounded startup-adjacent hardening pass in that same track
  has now reviewed `backend/app/scripts/ensure_admin.py`, keeping create-only
  bootstrap available while requiring `ADMIN_ALLOW_UPDATE=1` before mutating an
  existing matched user, and aligning the nearest docs/config examples to that
  explicit helper contract
- the twenty-sixth bounded startup-docs pass in that same track has now added
  a canonical operator command map in `docs/OPERATOR_STARTUP_COMMANDS.md` and
  aligned the root, ops, and production runbooks to the same explicit command
  story without changing behavior again

Current honest next step inside this track:

- stop here; the bounded operator-first startup lane is sufficiently complete

### What has already been done in this track

- `/api/v1/appointments/stats` marked deprecated in OpenAPI
- `/api/v1/appointments/qrcode` marked deprecated in OpenAPI
- legacy `/api/v1/board/state` marked deprecated in OpenAPI
- `queues.stats` compatibility fields `is_open` and `start_number` marked
  deprecated
- board legacy fallback reviewed and reframed as compatibility/rollback path

### Cleanup progress already made

Service-side duplicate / unmounted mirrors removed:

- `appointments_api_service.py`
- `visit_confirmation_api_service.py`
- `online_queue_legacy_api_service.py`
- `online_queue_new_api_service.py`
- `registrar_batch_api_service.py`
- `registrar_wizard_api_service.py`
- `registrar_integration_api_service.py`
- `queue_batch_service.py`
- `print_api_api_service.py`
- `print_templates_api_service.py`
- `qr_queue_api_service.py`
- `api_documentation_api_service.py`
- `docs_api_service.py`
- `health_api_service.py`
- `monitoring_api_service.py`

Bounded continuation after that baseline also removed additional detached
service-side duplicates and endpoint residues across:

- admin clinic / admin display / admin stats / admin doctors / admin telegram
- analytics, AI analytics/gateway, and observability follow-up surfaces
- telegram notification / webhook / bot / integration follow-up surfaces
- mobile extended, doctor info, medical equipment, telemetry, reports, SMS, and
  user-data-transfer follow-up surfaces

Current verdict:

- the clean low-risk duplicate pool is now nearly exhausted
- the remaining residue is increasingly behavior-bearing or protected
- the `admin_providers` protected duplicate has now been resolved through
  dedicated endpoint proof and cleanup
- the `payment_settings` protected residue pair has now also been resolved
- the `admin_users` auth-adjacent protected pair has now also been resolved
  through dedicated endpoint/RBAC proof and cleanup
- the `minimal_auth` auth-adjacent protected pair has now also been resolved
  through dedicated endpoint proof and cleanup
- the `simple_auth` auth-adjacent protected pair has now also been resolved
  through dedicated endpoint proof and cleanup
- the `password_reset` auth-adjacent protected pair has now also been resolved
  through dedicated endpoint proof, cleanup, and a narrow mounted-owner RBAC
  drift fix
- the `phone_verification` auth-adjacent protected pair has now also been
  resolved through dedicated endpoint proof, cleanup, and narrow mounted-owner
  RBAC drift fixes
- the `two_factor_devices` auth-adjacent protected pair has now also been
  resolved through dedicated runtime-contract proof and cleanup
- the `two_factor_auth.py` versus `two_factor_devices.py` route shadowing
  around `GET/DELETE /api/v1/2fa/devices*` is now an explicit protected tail,
  not an assumed cleanup-safe surface
- the `two_factor_sms_email` auth-adjacent protected pair has now also been
  resolved through dedicated endpoint proof, cleanup, and a narrow live
  frontend/backend parity repair for the SMS/email request shape
- the `websocket_auth` auth-adjacent protected duplicate has now also been
  resolved through dedicated websocket runtime-contract proof, cleanup, and
  narrow mounted-owner parity fixes for the live `WSManager` interface
- the `queue_auto_close` and `wait_time_analytics` queue-adjacent protected
  duplicates have now also been resolved through dedicated endpoint proof,
  cleanup, and narrow mounted-owner SSOT RBAC fixes
- the `section_templates` EMR-adjacent protected pair has now also been
  resolved through dedicated endpoint proof and cleanup
- the `emr_export` EMR-adjacent protected pair has now also been resolved
  through dedicated endpoint proof and cleanup
- the `emr_versioning_enhanced` EMR-adjacent protected pair has now also been
  resolved through dedicated endpoint proof and cleanup
- the `emr_lab_integration` EMR-adjacent protected pair has now also been
  resolved through dedicated endpoint proof and cleanup
- the mixed `/api/v1/2fa/devices*` route ownership tail has now been resolved
  as a published-contract issue; runtime first-match still belongs to
  `two_factor_auth.py`, and published OpenAPI now matches that live contract
  for the shadowed `GET/DELETE` operations without router reordering

Endpoint-side dead artifacts removed:

- `backend/app/api/v1/endpoints/online_queue.py`
- `backend/app/api/v1/endpoints/online_queue_legacy.py`
- `backend/app/api/v1/endpoints/monitoring.py`

Supporting cleanup already completed:

- stale `test_queue_batch_service.py` removed
- stale service-boundary checks updated where needed
- stale monitoring docs corrected to live `/system/monitoring/*`

## Current working rules

Continue with:

- review-first bounded slices
- one low-risk candidate at a time
- no broad refactors
- no runtime behavior changes unless the slice is a narrowly verified drift fix
- no touching blocked tails without a fresh contract/decision pass

For cleanup candidates:

1. verify mounted vs unmounted status
2. verify no live source imports
3. verify no live frontend/runtime dependency
4. fix stale docs if the removed surface was still documented
5. run verification

## Default verification commands

- `cd C:\final\backend && pytest tests/test_openapi_contract.py -q`
- `cd C:\final\backend && pytest -q`

Current known good signal:

- OpenAPI contract: `14 passed`
- full backend suite: `850 passed, 3 skipped`

## Recommended next execution unit

Current best next slice:

`stop here; current startup hardening step is sufficient`

Why this is now the best immediate move:

- status/backlog sync and residue bucketing are already in place
- non-protected mixed-risk residue (`settings`, `activation`, `clinic_management`)
  has been resolved
- `admin_providers` has been resolved with dedicated endpoint proof
- `payment_settings` has also been resolved with dedicated endpoint proof
- `admin_users` has also been resolved with dedicated endpoint/RBAC proof
- `minimal_auth` has also been resolved with dedicated endpoint proof
- `simple_auth` has also been resolved with dedicated endpoint proof
- `password_reset` has also been resolved with dedicated endpoint proof plus a
  narrow mounted-owner RBAC fix
- `phone_verification` has also been resolved with dedicated endpoint proof
  plus narrow mounted-owner RBAC fixes
- `two_factor_devices` has also been resolved with dedicated runtime-contract
  proof and cleanup
- `two_factor_sms_email` has also been resolved with dedicated endpoint proof,
  cleanup, and a narrow frontend parity repair
- `websocket_auth` has also been resolved with dedicated websocket
  runtime-contract proof, cleanup, and narrow mounted-owner parity fixes
- `queue_auto_close` and `wait_time_analytics` have also been resolved with
  dedicated endpoint proof, cleanup, and narrow mounted-owner SSOT RBAC fixes
- the protected auth-adjacent, queue-adjacent, and EMR duplicate queues are
  now exhausted; `section_templates`, `emr_export`,
  `emr_versioning_enhanced`, `emr_lab_integration`, `emr_ai`, and
  `emr_ai_enhanced` have all been resolved
- the mixed `/api/v1/2fa/devices*` route ownership is now documented and
  parity-aligned, not an active protected blocker
- `cashier` remains a payment-critical architecture review outside cleanup
- remaining progress now favors docs/status consolidation over more protected
  cleanup or parity work
- the broader `API_REFERENCE.md`, production-doc, env-template, compose
  support-file, and entrypoint fallback passes are now substantially complete
- the remaining visible ops/startup tail is no longer implicit startup
  mutation; that part is now hardened
- the main remaining gaps in this lane are no longer urgent behavior or docs
  inconsistencies
- startup, explicit admin bootstrap, and the command/runbook story are now
  aligned
- further work here is optional polish rather than the next must-do slice

## Strategic conclusion

The original “big plan” was not abandoned; it was largely executed and then
spread across many status documents as the work became more concrete.

The current reality is:

- the core architecture phase is largely complete
- the Postgres-sensitive regression guard is in place
- the remaining work is mostly legacy/deprecation tail handling
- the active engineering posture should now be:

`small honest cleanup + deprecation slices, while blocked semantic tails wait`
