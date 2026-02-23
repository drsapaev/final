# Load Testing Runbook

## Goal
- Validate baseline throughput and latency for critical public API endpoints.
- Detect regressions against stored baseline targets.
- Enforce per-profile capacity budgets for critical endpoint groups.

## Assets
- k6 scenario: `ops/load/clinic_core.js`
- Baseline and thresholds: `ops/load/baseline_targets.json`
- Profile budgets and endpoint groups: `ops/load/endpoint_profiles.json`
- Regression checker: `ops/scripts/check_load_regression.py`
- Profile runner/orchestrator: `ops/scripts/run_load_profiles.py`

## CI Execution
- Workflow job: `load-tests-nightly`
- Triggers:
  - nightly schedule
  - manual dispatch
  - `push` to `main`
- Artifacts:
  - `k6-summary.json`
  - `load-regression-report.md`
  - `load-regression-report.json`
  - `profiles/*` (per-profile summaries/reports)

## Target KPIs
- `core_readiness`: `RPS >= 25`, `P95 < 500ms`
- `queue_public`: `RPS >= 15`, `P95 < 700ms`
- `activation_public`: `RPS >= 15`, `P95 < 700ms`
- For every profile: `error_rate < 1%`, `checks_success >= 99%`

## Regression Policy
- `core_readiness`: RPS drop > 15% or P95 increase > 20% fails.
- `queue_public` / `activation_public`: RPS drop > 20% or P95 increase > 25% fails.

## Local Run
1. Start API on `http://127.0.0.1:8000`.
2. Run all profiles:
   - `python ops/scripts/run_load_profiles.py --config ops/load/endpoint_profiles.json --workspace ${PWD} --artifacts-dir artifacts/load --base-url http://127.0.0.1:8000 --api-ready 1`
3. Optional single-profile check:
   - `python ops/scripts/check_load_regression.py --summary artifacts/load/profiles/core_readiness/k6-summary.json --baseline ops/load/endpoint_profiles.json --profile core_readiness --report artifacts/load/profiles/core_readiness/load-regression-report.md`
