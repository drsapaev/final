# VPS Proof Track Workitems

## 1. Prepare the proof bundle
- Goal: assemble the exact source-of-truth set used for the VPS promotion rehearsal.
- Exact files/areas:
  - `docs/recovery/VPS_PROMOTION_READINESS_MATRIX.md`
  - `docs/recovery/VPS_PROMOTION_PROOF_GAPS.md`
  - `docs/recovery/VPS_PROMOTION_CRITICAL_GAPS.md`
  - `docs/recovery/VPS_PROMOTION_MINIMAL_TRACK.md`
  - `docs/runbooks/VPS_HOST_ROLLOUT_RUNBOOK.md`
  - `ops/vps/*`
  - `ops/load/*`
  - `.github/workflows/load-testing.yml`
  - `.github/workflows/monitoring.yml`
- Type: doc update
- Entry criteria: readiness audit complete and verdict is `NOT YET, BUT CLOSE`
- Exit criteria: all proof sources are linked and the track is obviously proof-first
- Required evidence: link list / index and scope note
- Risk: low
- Owner lane: docs / ops coordination

## 2. Rehearse VPS staging deploy
- Goal: prove the host deployment kit can deploy the current mainline release to a VPS staging host.
- Exact files/areas:
  - `ops/vps/scripts/deploy_host.sh`
  - `ops/vps/scripts/bootstrap_postgres.sh`
  - `ops/vps/backend.env.sample`
  - `ops/vps/frontend.env.sample`
  - `ops/vps/systemd/clinic-backend.service.template`
  - `ops/vps/nginx/clinic.conf.template`
  - `docs/runbooks/VPS_HOST_ROLLOUT_RUNBOOK.md`
- Type: rehearsal
- Entry criteria: proof bundle prepared and host credentials / environment are ready
- Exit criteria: a fresh VPS staging deploy completes and reaches healthy services
- Required evidence: command log, service status, health-check output, deploy transcript
- Risk: high
- Owner lane: ops / infra

## 3. Prove cutover and rollback
- Goal: verify the cutover path and the rollback path are both executable and understandable.
- Exact files/areas:
  - `ops/vps/scripts/run_cutover.sh`
  - `ops/vps/scripts/check_health.sh`
  - `docs/runbooks/VPS_HOST_ROLLOUT_RUNBOOK.md`
  - `docs/runbooks/POSTGRES_DR_RUNBOOK.md`
- Type: rehearsal
- Entry criteria: staging deploy is healthy
- Exit criteria: cutover completes, rollback is demonstrated, and post-rollback health is verified
- Required evidence: before/after state, rollback log, health snapshots
- Risk: high
- Owner lane: ops / database / release

## 4. Validate soak and load budgets
- Goal: prove the published critical-profile budgets are respected on the promotion path.
- Exact files/areas:
  - `ops/load/clinic_core.js`
  - `ops/load/endpoint_profiles.json`
  - `ops/load/baseline_targets.json`
  - `docs/runbooks/LOAD_TESTING_RUNBOOK.md`
  - `.github/workflows/load-testing.yml`
- Type: proof
- Entry criteria: deploy and cutover rehearsals are successful
- Exit criteria: soak run finishes with thresholds inside budget or with an approved exception
- Required evidence: k6 output, threshold summary, regression notes
- Risk: medium-high
- Owner lane: perf / ops

## 5. Prove observability SLA loop
- Goal: demonstrate that logs, metrics, and alerting are adequate for the promotion path.
- Exact files/areas:
  - `docs/runbooks/OBSERVABILITY_SLA_RUNBOOK.md`
  - `.github/workflows/monitoring.yml`
  - `docs/PRODUCTION_SECURITY.md`
- Type: proof
- Entry criteria: deployment and soak are runnable
- Exit criteria: metrics are visible, alerts are observed, and the review loop is completed
- Required evidence: metrics snapshots, alert evidence, review notes
- Risk: medium
- Owner lane: ops / monitoring

## 6. Verify tenant isolation on the promotion path
- Goal: prove multi-clinic / tenant-scope enforcement survives the VPS promotion flow.
- Exact files/areas:
  - `backend/app/core/tenant_scope.py`
  - `backend/app/middleware/tenant_scope_middleware.py`
  - `backend/app/core/config.py`
  - `docs/architecture/INTEROPERABILITY_MULTI_CLINIC.md`
  - `docs/ROLES_AND_ROUTING.md`
  - `docs/ROLE_SYSTEM_PROTECTION.md`
- Type: proof
- Entry criteria: staging host is up and the rollout path is runnable
- Exit criteria: scoped requests, branch isolation, and least-privilege assertions pass in the promoted environment
- Required evidence: request traces, assertion logs, scenario notes
- Risk: medium-high
- Owner lane: backend / security / ops

