# VPS Promotion Readiness Matrix

| Dimension | Status | Evidence | Missing proof | Risk | Recommendation |
|---|---|---|---|---|---|
| Host deployment kit completeness | MOSTLY_READY | `ops/vps/*`, `docs/runbooks/VPS_HOST_ROLLOUT_RUNBOOK.md` | A live VPS rehearsal with the exact kit | Medium | Keep kit, add proof run |
| Environment/config readiness | READY | backend/frontend staging env samples, VPS templates | None critical; verify secrets handling on host | Low | Keep current |
| Database/bootstrap/migration readiness | MOSTLY_READY | `bootstrap_postgres.sh`, `deploy_host.sh`, Postgres DR docs | VPS-side full bootstrap + upgrade replay evidence | Medium | Validate during staging promotion |
| Reverse proxy / systemd / process control readiness | MOSTLY_READY | Nginx and systemd templates, deploy script | Real host restart / failure recovery evidence | Medium | Validate on VPS staging |
| Cutover / rollback / health-check readiness | PARTIAL | `run_cutover.sh`, `check_health.sh`, runbooks | Rollback drill, health-check timing and failure proof | High | Make rollback proof the first gap to close |
| Local staging -> VPS promotion path clarity | READY | `LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md`, VPS runbook, staging scripts | None material; path is documented | Low | Keep current |
| Evidence of staging acceptance already completed | MOSTLY_READY | parity and UX scorecards, readiness checklist | VPS staging execution proof, not just local evidence | Medium | Distinguish local acceptance from VPS proof |
| Observability / monitoring / alerting readiness | PARTIAL | observability runbook, monitoring workflow | Alert verification, SLA loop rehearsal, actual operational proof | High | Add a proof track |
| Load-budget / performance validation readiness | PARTIAL | load profiles, thresholds, load-testing workflow | Recent production-like soak on the promotion path | High | Run a narrow soak proof |
| Multi-clinic / tenant isolation readiness | PARTIAL | tenant scope middleware, interoperability docs, role checks | End-to-end promotion-path proof under multi-clinic scenarios | High | Verify on staging host before rollout |
| Security / secrets / least-privilege readiness | MOSTLY_READY | `PRODUCTION_SECURITY.md`, env samples, scopes | Host-level secret handling confirmation | Medium | Review as part of staging promotion |
| Documentation / runbook consistency | PARTIAL | runbooks and ops docs exist | Some docs still mix legacy and current truth | Medium | Update or mark stale after proof |

