# Load Testing Runbook

## Goal
- Validate baseline throughput and latency for critical public API endpoints.
- Detect regressions against stored baseline targets.

## Assets
- k6 scenario: `ops/load/clinic_core.js`
- Baseline and thresholds: `ops/load/baseline_targets.json`
- Regression checker: `ops/scripts/check_load_regression.py`

## CI Execution
- Workflow job: `load-tests-nightly`
- Triggers:
  - nightly schedule
  - manual dispatch
- Artifacts:
  - `k6-summary.json`
  - `load-regression-report.md`

## Target KPIs
- `RPS >= 25`
- `P95 < 500ms`
- `error_rate < 1%`
- `checks_success >= 99%`

## Regression Policy
- RPS drop > 15% from baseline fails.
- P95 increase > 20% from baseline fails.

## Local Run
1. Start API on `http://127.0.0.1:8000`.
2. Run k6:
   - `docker run --rm --network=host -e BASE_URL=http://127.0.0.1:8000 -v ${PWD}/ops/load:/scripts -v ${PWD}/artifacts/load:/artifacts grafana/k6 run /scripts/clinic_core.js --summary-export=/artifacts/k6-summary.json`
3. Check regression:
   - `python ops/scripts/check_load_regression.py --summary artifacts/load/k6-summary.json --baseline ops/load/baseline_targets.json --report artifacts/load/load-regression-report.md`
