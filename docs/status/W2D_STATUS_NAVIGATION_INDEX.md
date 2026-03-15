# W2D Status Navigation Index

Updated: 2026-03-14
Status: current navigation landing page

## Purpose

Use this file as the shortest navigation entry point into the current W2D
status/doc trail.

If you only open one status doc first, start here and then jump into the
current source-of-truth docs below.

## Current Source of Truth

- `docs/status/AI_FACTORY_OPENHANDS_MASTER_PLAN.md`
  - canonical execution/status doc
- `docs/status/OPENHANDS_TASK_BACKLOG.md`
  - shorter execution index aligned to the master plan
- `docs/architecture/W2D_REMAINING_RESIDUE_STRATEGIC_AUDIT.md`
  - current residue classification and “what is not cleanup” map

## Latest Completed Status-Docs Consolidation Passes

- `docs/architecture/W2D_2FA_DEVICES_OPENAPI_PARITY_RESTORATION.md`
  - closed the final active protected 2FA parity tail
- `docs/architecture/W2D_STATUS_POINTER_CONSOLIDATION_AFTER_2FA_PARITY.md`
  - normalized late protected `NEXT_EXECUTION_UNIT_AFTER_*` docs as historical
    pointers
- `docs/architecture/W2D_STATUS_NAVIGATION_INDEX_CLEANUP.md`
  - added this landing page and linked it into the current status flow
- `docs/architecture/W2D_API_REFERENCE_SETTINGS_NOTIFICATIONS_VERIFICATION.md`
  - started the bounded `API_REFERENCE.md` docs-vs-code track
- `docs/architecture/W2D_API_REFERENCE_AUTH_USERS_VERIFICATION.md`
  - corrected the live `Authentication` and `Users` drift in that same track
- `docs/architecture/W2D_API_REFERENCE_QUEUE_VERIFICATION.md`
  - corrected the live `Queue` drift and split the docs between modern queue
    surfaces and legacy compatibility routes
- `docs/architecture/W2D_API_REFERENCE_PAYMENTS_VERIFICATION.md`
  - corrected the protected payments docs drift while keeping the slice
    docs-only
- `docs/architecture/W2D_API_REFERENCE_ANALYTICS_VERIFICATION.md`
  - corrected the live analytics docs drift and reframed that section around
    current route families
- `docs/architecture/W2D_API_REFERENCE_DEPARTMENTS_SERVICES_VERIFICATION.md`
  - corrected the live departments/services docs drift and removed stale
    department CRUD plus the old narrow services route summary
- `docs/architecture/W2D_API_REFERENCE_DOCTORS_APPOINTMENTS_VERIFICATION.md`
  - corrected the stale `/doctors/*` narrative and added a curated operational
    `/appointments*` map
- `docs/architecture/W2D_API_REFERENCE_PWA_VISITS_VERIFICATION.md`
  - corrected the patient portal route-prefix drift and reframed visits around
    the live `/visits/visits*` surface
- `docs/architecture/W2D_API_REFERENCE_PATIENTS_SCHEDULE_VERIFICATION.md`
  - corrected the broader patients registry map and added the missing curated
    `/schedule*` section
- `docs/architecture/W2D_API_REFERENCE_HEALTH_AUTH_HEADER_VERIFICATION.md`
  - corrected footer-level health/auth-header drift and tied auth guidance to
    the published security scheme
- `docs/architecture/W2D_API_REFERENCE_STATUS_CODES_ROLES_VERIFICATION.md`
  - corrected the generic footer status/roles summaries into a bounded
    response-pattern and RBAC-glossary pass
- `docs/architecture/W2D_API_REFERENCE_NEW_MODULES_LINKS_VERIFICATION.md`
  - corrected the last stale `API_REFERENCE.md` footer families and navigation
  links, and shifted the next docs target to the mounted custom
  `/api/v1/docs/*` pages
- `docs/architecture/W2D_CUSTOM_DOCS_ENDPOINTS_VERIFICATION.md`
  - corrected the mounted `/api/v1/docs/*` helper endpoints so they now point
    back to generated docs and live schema data instead of serving a stale
    hand-written mini-spec
- `docs/architecture/W2D_API_DOCUMENTATION_ROUTER_VERIFICATION.md`
  - corrected the neighboring `/api/v1/documentation/*` helper router so it
  now serves generated summaries and live helper guidance instead of a stale
  hand-written route manual
- `docs/architecture/W2D_PRODUCTION_READINESS_REPORT_VERIFICATION.md`
  - reframed the production readiness memo as a historical snapshot and pointed
    readers back to the current SSOT and current verification baseline
- `docs/architecture/W2D_SETUP_PRODUCTION_VERIFICATION.md`
  - reframed the neighboring setup guide and summary into curated setup docs
    with explicit compose/env/monitoring caveats instead of drop-in production
    claims
- `docs/architecture/W2D_PRODUCTION_READINESS_CHECKLIST_VERIFICATION.md`
  - reframed the neighboring readiness checklist into an archived FK/schema
    integrity doc with explicit script-scope caveats instead of a whole-system
    production verdict
- `docs/architecture/W2D_OPS_README_ENV_VERIFICATION.md`
  - normalized the ops README and coupled env example into clearer
    compose-oriented docs with explicit env-layer and legacy-auth caveats
- `docs/architecture/W2D_ENV_SETUP_GUIDE_VERIFICATION.md`
  - normalized the backend env quick-start guide so it now points back to the
    live env templates and current setup docs instead of duplicating stale env
    guidance
- `docs/architecture/W2D_BACKEND_ENV_EXAMPLE_VERIFICATION.md`
  - normalized the backend env template itself so it now matches the current
    config and newer env docs more honestly
- `docs/architecture/W2D_DOCKER_COMPOSE_SUPPORT_FILE_VERIFICATION.md`
  - corrected the real compose support-file path wiring so build contexts,
    bind mounts, and `env_file` now resolve against the repo layout instead of
    a broken `ops/`-local pseudo-layout
- `docs/architecture/W2D_BACKEND_ENTRYPOINT_SUPPORT_FILE_VERIFICATION.md`
  - aligned the entrypoint SQLite fallback with the current backend
    env/config story and separated the remaining startup semantics into an
    explicit review-required tail
- `docs/architecture/W2D_BACKEND_ENTRYPOINT_STARTUP_SEMANTICS_PLAN_GATE.md`
  - opened the explicit plan gate for metadata schema bootstrap and default
  auto-admin behavior, and tightened the neighboring ops/production docs so
  those startup semantics are no longer implicit
- `docs/architecture/W2D_OPERATOR_FIRST_STARTUP.md`
  - executed the startup hardening decision, removed implicit schema bootstrap,
    made admin bootstrap opt-in, and documented the explicit operator-first
    startup flow
- `docs/architecture/W2D_ENSURE_ADMIN_CONTRACT_REVIEW.md`
  - hardened the explicit admin-bootstrap helper so existing-user mutation now
    requires `ADMIN_ALLOW_UPDATE=1`
- `docs/architecture/W2D_OPERATOR_RUNBOOK_COMMAND_NORMALIZATION.md`
  - added a canonical operator startup command map and aligned root, ops, and
    production docs to the same explicit flow

## Current Next-Step Pointer

- `docs/status/W2D_NEXT_EXECUTION_UNIT_AFTER_OPERATOR_RUNBOOK_COMMAND_NORMALIZATION.md`
  - current follow-up after the bounded operator-first startup lane

## Historical Re-Entry Docs

These are still useful, but they are no longer the primary entry point and now
carry explicit historical/current-SSOT framing:

- `docs/status/W2D_THREAD_HANDOFF.md`
- `docs/status/OPENHANDS_FIRST_10_TASKS.md`
- `docs/status/AI_FACTORY_OPENHANDS_PRECHECK.md`

## Historical Late Protected Pointer Chain

These documents preserve execution history for the late protected cleanup lane,
but they should now be read as archive records, not as the current queue.

The normalization trail for that chain is recorded in:

- `docs/architecture/W2D_STATUS_POINTER_CONSOLIDATION_AFTER_2FA_PARITY.md`

## Current Verification Baseline

- `cd C:\final\backend && pytest tests/test_openapi_contract.py -q`
  - `14 passed`
- `cd C:\final\backend && pytest -q`
  - `850 passed, 3 skipped`

## Reader Rule

When a historical status doc and the master plan disagree:

- trust `AI_FACTORY_OPENHANDS_MASTER_PLAN.md`
- use this navigation index to find the newest related W2D doc
- treat older `NEXT_EXECUTION_UNIT_AFTER_*` files as execution history unless
  they explicitly say they are current
