# VPS Promotion Source Inventory

## Current source-of-truth candidates

| Path | Type | Intended role | Status |
|---|---|---|---|
| `ops/vps/README.md` | runbook | VPS host promotion kit and rollout order | current, but mixed with legacy wording in adjacent ops docs |
| `ops/vps/backend.env.sample` | env sample | staging / host backend environment defaults | current |
| `ops/vps/frontend.env.sample` | env sample | staging frontend endpoint configuration | current |
| `ops/vps/nginx/clinic.conf.template` | template | reverse proxy + static frontend config | current |
| `ops/vps/systemd/clinic-backend.service.template` | template | backend process control on VPS | current |
| `ops/vps/scripts/bootstrap_postgres.sh` | script | bootstrap Postgres role/db | current |
| `ops/vps/scripts/deploy_host.sh` | script | host deploy, migrate, build, render, restart | current |
| `ops/vps/scripts/run_cutover.sh` | script | EMR cutover on staging/production hosts | current |
| `ops/vps/scripts/check_health.sh` | script | host and public health checks | current |
| `ops/compose.staging.yml` | compose | host-like staging stack | current |
| `ops/scripts/start_staging_host.ps1` | script | local Windows staging host boot | current, proof helper |
| `ops/scripts/run_staging_cutover_host.ps1` | script | local Windows cutover rehearsal | current, proof helper |
| `ops/scripts/stop_staging_host.ps1` | script | local Windows staging host teardown | current, proof helper |
| `ops/load/clinic_core.js` | load profile | k6 load threshold definitions | current |
| `ops/load/endpoint_profiles.json` | load profile | load budgets and regression thresholds | current |
| `ops/load/baseline_targets.json` | load baseline | baseline defaults for load runs | current |
| `docs/runbooks/VPS_HOST_ROLLOUT_RUNBOOK.md` | runbook | VPS promotion end-to-end procedure | current |
| `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md` | runbook | local host-based staging acceptance | current |
| `docs/runbooks/LOAD_TESTING_RUNBOOK.md` | runbook | load validation and regression gates | current |
| `docs/runbooks/OBSERVABILITY_SLA_RUNBOOK.md` | runbook | metrics, logs, alerts, review loop | current |
| `docs/runbooks/POSTGRES_DR_RUNBOOK.md` | runbook | database backup/restore recovery | current but not VPS-specific proof |
| `docs/CI_GUARDRAILS.md` | report | merge / parity / role-system gates | current evidence |
| `docs/PRODUCTION_SECURITY.md` | report | secrets, CORS, logging, rate limiting | current evidence |
| `docs/PLAN_CHECKLIST.md` | tracker | readiness tracker with staging/prod milestone notes | current evidence, partially declarative |
| `docs/BACKUP_RESTORE_PROCEDURES.md` | runbook | backup/restore strategy | current evidence |
| `docs/architecture/INTEROPERABILITY_MULTI_CLINIC.md` | architecture note | tenant / branch isolation model | current evidence, partly implementation-oriented |
| `docs/reports/FRONTEND_BACKEND_PARITY_REPORT.md` | report | parity and RBAC evidence | historical evidence only |
| `docs/reports/FRONTEND_UX_CORRECTNESS_SCORECARD.md` | report | UX correctness evidence | historical evidence only |
| `.github/workflows/ci-cd-unified.yml` | workflow | CI/CD gate | current |
| `.github/workflows/load-testing.yml` | workflow | load testing automation | current |
| `.github/workflows/monitoring.yml` | workflow | observability jobs | current, manual-only / partial |
| `.github/workflows/security-scan.yml` | workflow | security scanning gate | current |
| `.github/workflows/role-system-check.yml` | workflow | role-system regression gate | current |
| `backend/staging.env.sample` | env sample | backend staging defaults | current |
| `frontend/staging.env.sample` | env sample | frontend staging defaults | current |
| `backend/.env.example` | env sample | backend local defaults | current, not deployment truth |
| `frontend/.env.example` | env sample | frontend local defaults | current, not deployment truth |

## Historical / stale / partial material
- `ops/README.md` mixes legacy Docker/SQLite-first language with current VPS guidance
- `ops/docker-compose.yml` is legacy and not the preferred VPS path
- `docs/reports/*` are evidence artifacts, not operational proof by themselves
- `docs/PLAN_CHECKLIST.md` is useful as a tracker but contains declarative readiness claims that still need VPS proof

