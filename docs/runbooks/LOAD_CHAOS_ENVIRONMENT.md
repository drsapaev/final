# Load / Chaos CI — Environment Contract

Status: active · Owner: CI/reliability · Created: 2026-08-16 (post-vacuous-run findings)

This document is the contract between `load.yml` / `chaos.yml` and the system
under test. Rule of order: **the environment contract comes before fixing the
tests** — a green workflow that cannot reach its subject tests nothing.

## 1. load.yml (k6)

### Required services (all mandatory, all inside the job)

| Service | Provisioning | Readiness proof (hard gate) |
|---|---|---|
| PostgreSQL 16 | `services: postgres` container | `SELECT 1` retry loop (≤30×2s), then `alembic upgrade head` must succeed |
| Backend API | `uvicorn app.main:app --port 8000` (background) with `DATABASE_URL`, `TESTING=1`, `CORS_DISABLE=1` | `GET /health` → 200, ≤30×2s retries; failing readiness fails the job |
| Test user + JWT | seed via `python -m app.scripts.dev_seed` (or synthetic seed), then `POST /api/v1/authentication/login` with seeded credentials | login response contains `access_token`; no secrets required |

### k6 execution semantics

- Scripts: `tests/load/k6-queue-load.js`, `k6-emr-load.js`; 2m stage profile each.
- `BASE_URL=http://localhost:8000`; `TEST_JWT` from the login step above —
  never a placeholder (`test-token` fallback is forbidden).
- **GitHub-hosted runner = reference-only** for absolute latency (shared
  hardware): k6 `p(95)` thresholds are recorded and compared to
  `e2e/k6/baseline.json` informationally; the **error rate threshold is
  enforced** regardless of runner (connection/auth errors are never
  acceptable on any runner).
- Self-hosted runner: full enforcement (error rate + p95 + baseline gate).

### Anti-vacuous guarantees (the rules this contract exists for)

1. Missing environment readiness ⇒ job FAILS (no silent skip).
2. k6 producing no results file ⇒ job FAILS (`if-no-files-found: error` on
   the results artifact).
3. `continue-on-error` on k6 steps is forbidden — a failed run must surface.

## 2. chaos.yml (Playwright)

### Required services

| Service | Provisioning | Readiness proof |
|---|---|---|
| Frontend dev server | Playwright `webServer` (`npm run dev`, :5173) | Playwright's built-in URL polling |

- **No backend required by design**: chaos specs inject failures via
  `page.route` mocks and verify recovery in-page.
- Install: `npm ci` with the repo `frontend/.npmrc` (`legacy-peer-deps`).

### Execution semantics

- **Phase 1 (failure injection)**: `continue-on-error` is allowed — injected
  failures are the point — but the phase must EXECUTE the full spec set
  (test-count recorded; zero executed tests ⇒ FAIL, not skip).
- **Phase 2 (recovery)**: all tests must pass; no masking.

### Anti-vacuous guarantees

Same three rules as load.yml (readiness, results presence, no masking of
phase-2 failures).

## 3. Shared rules

- Both jobs run weekly on schedule (Sun) + dispatch; failures alert via the
  R1 `notify-failure` action (issue with `ci-failure` label).
- Artifacts (k6 NDJSON, playwright reports) are mandatory uploads.
- Any change that weakens one of the anti-vacuous guarantees requires an ADR
  note, not a comment.
