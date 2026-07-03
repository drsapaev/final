# CI/CD Reference

> **Canonical source of truth** for what CI/CD does on this repo.
> Replaces the four competing docs that used to live at the repo root:
> `CI-CD-README.md`, `README-CI-CD.md`, `SETUP-CI-CD.md`,
> `CI_CD_FINAL_STATUS_REPORT.md`. Those have been archived to
> `docs/archive/`.

## Workflows (`.github/workflows/`)

| Workflow | Triggers | Blocks merge? | Purpose |
|---|---|---|---|
| `ci-cd-unified.yml` | push(main,develop), PR(main), daily 02:00 UTC, manual | ✅ Yes | The main pipeline. Backend pytest with PG 16, frontend lint+unit+build, parity checks, registrar-time Playwright e2e. Defines required merge blockers. |
| `security-scan.yml` | push(main,develop), PR(main,develop), daily 03:00 UTC | ✅ Yes (since P0.1) | `bandit -ll` (MEDIUM+ findings block), `safety check` (any CVE blocks), `pip-audit` (report-only). Uploads SARIF/JSON artifacts. |
| `gitleaks.yml` | push(main,develop), PR(main,develop), daily 03:30 UTC | ✅ Yes (since P0.2) | Full-repo secret scan with custom rules for Telegram bot tokens, Click.uz, Payme, DeepSeek, Grok. |
| `role-system-check.yml` | push/PR on path filters (App.jsx, Login.jsx, UserSelect.jsx, role endpoints, role_validation.py, test_rbac_matrix.py) | ✅ Yes | PG 16 service + `tests/integration/test_rbac_matrix.py`. Falls back to `scripts/ci/validate_role_integrity.py` if pytest exits 4. |
| `pr-review-quality-gate.yml` | PR events on main | ✅ Yes | Runs `scripts/run_pr_review_gate_checks.py` against the PR body — enforces evidence-based PR template. |
| `pr-lifecycle-recommendation.yml` | PR events on main | ❌ No | Adds lifecycle labels + bot comment via `actions/github-script@v9`. Cosmetic. |
| `format-code.yml` | push on `backend/**/*.py`, `frontend/**/*.{js,jsx,ts,tsx}`, manual | ❌ No (report-only) | `black --check`, `isort --check`, `npm run lint:check`. Warnings only — enforcement happens in pre-commit. |
| `weekly-maintenance.yml` | Weekly Sunday 22:30 UTC + manual | ❌ No | npm audit + pip-audit + runs `backend/tests/architecture` and `backend/tests/unit`. Writes TSV summary. |

**Deleted in P0.8:**
- ~~`monitoring.yml`~~ — schedule was disabled, ran against a CI-started uvicorn on a temp PG, generated fake "✅ Доступна" reports regardless of actual endpoint state. Replaced by Sentry (frontend, P0.7) + Prometheus (backend, P1).
- ~~`load-testing.yml`~~ — always returned success, threshold was 30% success rate with explicit comment "Не блокируем CI/CD". Replaced by k6 or locust script TBD (P2).

## Required merge blockers

Per `ci-cd-unified.yml`, a PR to `main` cannot merge until **all** of these
pass:

1. `backend-pytest` (PG 16 service, full unit + integration suite)
2. `frontend-lint-unit`
3. `frontend-build`
4. `frontend-backend-parity` (contract tests)
5. `context-boundary-integrity` (no cross-layer imports)
6. `registrar-time-e2e` (Playwright, path-filtered)

Plus, on every PR:
- `security-scan.yml` (bandit MEDIUM+, safety CVEs)
- `gitleaks.yml` (secret scan)
- `role-system-check.yml` (RBAC matrix — path-filtered)
- `pr-review-quality-gate.yml` (PR template compliance)

## Branch protection (settings → branches → main)

Required: ✅ Require PR, ✅ Require status checks (all of the above),
✅ Require approvals (≥1), ✅ Dismiss stale approvals on new push,
✅ Require linear history.

`develop` is more permissive — direct pushes allowed for fast iteration,
but the same CI runs.

## Secrets & env vars (CI)

| Name | Used by | Notes |
|---|---|---|
| `GITHUB_TOKEN` (auto) | gitleaks, pr-lifecycle | Auto-provided by GitHub. |
| `clinic_ci_only_password` | ci-cd-unified, role-system-check | Placeholder password for PG 16 service. NOT a real secret — safe to inline. |
| `CODECOV_TOKEN` | ci-cd-unified (if re-enabled) | Optional. |

To add a new secret: Settings → Secrets and variables → Actions → New repository secret.

## Local pre-commit

`.pre-commit-config.yaml` runs:
- `pre-commit-hooks`: large files, merge conflicts, private keys, yaml/json/toml syntax, no-commit-to-main
- `gitleaks` (v8.21.2): same rules as CI
- `ruff` + `ruff-format`: Python lint + format (`backend/`)
- `black` (24.10.0): Python formatting (`backend/`)
- `eslint` (local hook via `npx`): frontend lint + autofix
- Custom: block `*.db`/`*.sqlite`/`*.dump`/`*.sql`, block real `.env` files, block `test_*.py` at root

Install: `pre-commit install`. Update: `pre-commit autoupdate`.

## Running CI locally

```bash
# Backend pytest (matches ci-cd-unified backend-pytest job)
cd backend && pytest -m "not slow"

# Frontend lint + unit (matches frontend-lint-unit job)
cd frontend && npm run lint:check && npm run test:unit

# Frontend build (matches frontend-build job)
cd frontend && npm run build

# Role matrix (matches role-system-check.yml)
cd backend && pytest tests/integration/test_rbac_matrix.py -v

# Security (matches security-scan.yml)
cd backend && bandit -r . -ll && safety check && pip-audit

# Secrets (matches gitleaks.yml)
gitleaks detect --source . --config .gitleaks.toml
```

## Adding a new workflow

1. Pick a name matching `<area>-<verb>.yml` (e.g. `docs-build.yml`, `migrations-check.yml`).
2. Triggers: prefer `pull_request` + narrow `paths` filter. Daily `schedule` only if truly periodic.
3. Permissions: `contents: read` by default. Add `pull-requests: write` only if you need to comment on PRs.
4. Concurrency: always set `cancel-in-progress: true` for PR events.
5. If the workflow should block merge, add it to the branch protection required status checks list.
6. Update the table at the top of this file.

## Deploy

- **Frontend**: Vercel. `vercel.json` enables deploys for `main`, `preview/**`, `ci/**` branches. Preview deploys on every PR.
- **Backend**: Docker Compose via `ops/compose.staging.yml` for staging. No production Dockerfile at root (TBD).
- **Database**: Alembic migrations run as part of the backend deploy. 31 migrations as of 2026-07.
