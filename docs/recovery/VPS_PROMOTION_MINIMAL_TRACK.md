# VPS Promotion Minimal Track

## Track name
VPS Promotion Proof Track

## Goal
Prove that the current `origin/main` can be promoted safely to a VPS-hosted staging/production-like environment with deploy, soak, rollback, observability, and isolation evidence.

## Work items

### 1. VPS staging deploy rehearsal
- Exact goal: run the host deployment flow from the current kit on a real or faithfully simulated VPS
- Likely touched areas: ops scripts, runbooks, deployment notes
- Type: proof/validation
- Entry criteria: host kit is complete and secrets/config are prepared
- Exit criteria: deploy completes successfully with recorded evidence
- Validation evidence required: command logs, health checks, service status
- Risk: high if hidden host assumptions fail

### 2. Cutover and rollback rehearsal
- Exact goal: prove the cutover script and rollback path are executable
- Likely touched areas: ops scripts, runbooks
- Type: proof/validation
- Entry criteria: staging deploy is successful
- Exit criteria: cutover and rollback both complete with no unresolved failures
- Validation evidence required: before/after state and rollback outcome
- Risk: high

### 3. Production-like soak with load budgets
- Exact goal: run the known load profiles against the promotion path and compare against thresholds
- Likely touched areas: load profiles, workflow notes, evidence docs
- Type: proof/validation
- Entry criteria: staging deploy is healthy
- Exit criteria: p95 / error rate / resource behavior stays within budget or gets a documented exception
- Validation evidence required: k6 output and threshold summary
- Risk: medium-high

### 4. Observability SLA review loop
- Exact goal: verify the metrics / alerting / review loop works during the rehearsal
- Likely touched areas: monitoring docs, workflow artifacts, ops evidence
- Type: proof/validation
- Entry criteria: deployment and soak are runnable
- Exit criteria: metrics and alerts are observed and reviewed successfully
- Validation evidence required: captured metrics, alert state, review notes
- Risk: medium

### 5. Tenant-isolation verification on staging promotion path
- Exact goal: prove multi-clinic / tenant scope assertions during promotion and soak
- Likely touched areas: tenant scope docs, test plan, validation notes
- Type: proof/validation
- Entry criteria: host rehearsal environment is available
- Exit criteria: isolation assertions pass for the selected tenant/branch scenarios
- Validation evidence required: request traces / assertions / test output
- Risk: medium-high

### 6. Docs reconciliation after proof
- Exact goal: mark stale ops docs and elevate proven runbooks to current source-of-truth status
- Likely touched areas: docs/runbooks, ops README
- Type: runbook/doc update
- Entry criteria: proof items above complete
- Exit criteria: docs clearly separate current truth from historical evidence
- Validation evidence required: doc diff and review
- Risk: low

