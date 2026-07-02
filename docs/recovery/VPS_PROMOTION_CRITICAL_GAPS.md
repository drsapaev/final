# VPS Promotion Critical Gaps

## 1. VPS staging execution / soak / rollback proof is missing
- Affected area: deployment readiness
- Why it matters: without a real rehearsal, host deploy and rollback remain theoretical
- Current evidence: scripts and runbooks exist
- Missing: a completed VPS staging rehearsal with deploy, soak, rollback, and health-check evidence
- Severity: P0
- Best action: validation/proof task

## 2. Observability SLA review loop is not proven end-to-end
- Affected area: monitoring / alerting
- Why it matters: promotion needs proof that metrics, alerts, and review workflow work under host conditions
- Current evidence: observability runbook and workflow exist
- Missing: evidence of a completed SLA loop on the promotion path
- Severity: P1
- Best action: validation/proof task

## 3. Load-budget enforcement on the promotion path is not proven
- Affected area: performance / soak
- Why it matters: thresholds exist, but promotion needs actual proof that the host path respects them
- Current evidence: k6 profiles and thresholds are defined
- Missing: a recent soak run tied to the VPS promotion path
- Severity: P1
- Best action: validation/proof task

## 4. Multi-clinic / tenant isolation is not verified on the promoted contour
- Affected area: security / isolation
- Why it matters: branch- and tenant-scoped behavior must hold on the host path, not just in architecture docs
- Current evidence: tenant scope middleware and contracts exist
- Missing: end-to-end promotion-path verification with isolation assertions
- Severity: P1
- Best action: validation/proof task

## 5. Documentation still mixes current and historical truth in some places
- Affected area: runbooks / docs consistency
- Why it matters: stale docs can cause unsafe rollout assumptions
- Current evidence: VPS docs are present, but some ops docs still mix legacy Docker/SQLite language
- Missing: cleanup / explicit historical labeling
- Severity: P2
- Best action: docs update only

