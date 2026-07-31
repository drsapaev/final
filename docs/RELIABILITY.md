# Reliability Dashboard

**Last updated:** 2026-07-31
**Status:** Initial — awaiting first scheduled CI runs

---

## Historical Trends

| Date | Mutation (Python) | Mutation (TS) | Queue p95 | EMR p95 | Chaos | Security | E2E |
|------|-------------------|---------------|-----------|---------|-------|----------|-----|
| 2026-07-31 | — (config ready) | — (config ready) | 310ms (baseline) | 1000ms (baseline) | 4 scenarios (Phase 1-3) | 15 scenarios | 10 scenarios |

**Legend:** `—` = not yet measured (awaiting first scheduled run). Numbers will be filled after nightly/weekly CI runs produce artifacts.

---

## Baseline Values

| Metric | Baseline | Threshold (×1.15) | Source |
|--------|----------|-------------------|--------|
| Queue p95 | 310ms | 356ms | `e2e/k6/baseline.json` |
| EMR p95 | 1000ms | 1150ms | `e2e/k6/baseline.json` |
| Mutation (Python) | ≥80% | — | `scripts/parse-mutmut-score.py` |
| Mutation (TS) | ≥70% | — | `scripts/parse-stryker-score.js` |

---

## CI Schedule

| Workflow | Schedule | What |
|----------|----------|------|
| `mutation.yml` | Nightly 02:00 UTC | mutmut (Python) + Stryker (TS) |
| `load.yml` | Weekly Sun 03:00 UTC | k6 queue + EMR with baseline × 1.15 gate |
| `chaos.yml` | Weekly Sun 04:00 UTC | Phase 1 failure → Phase 2 recovery → Phase 3 verification |
| `release-gate.yml` | On release | k6 baseline + incremental Stryker + regression |

---

## How to Update This Dashboard

After each scheduled CI run:

1. Download artifacts from GitHub Actions
2. Extract mutation scores from `mutmut-report` and `stryker-report` artifacts
3. Extract p95 latencies from `k6-results` artifact
4. Add a new row to the table above with the date and measurements
5. If any metric degraded >15% from baseline, create an issue

---

## Alert Pipeline

When a metric exceeds threshold:

1. **Load degradation (>15%):** `load-baseline-check.mjs` exits with code 1 → CI job fails → GitHub Actions notification
2. **Mutation score below threshold:** `parse-mutmut-score.py` or `parse-stryker-score.js` exits with code 1 → CI job fails
3. **Chaos recovery failure:** Phase 2/3 tests fail → CI job fails → team notified
4. **Security regression:** E2E security tests fail → CI job fails → immediate review required

All failures produce GitHub Actions artifacts for post-mortem analysis.
