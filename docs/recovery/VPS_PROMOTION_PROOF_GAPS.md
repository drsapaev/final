# VPS Promotion Proof Gaps

## Already proven in current `origin/main`

| Proof area | Evidence | Assessment |
|---|---|---|
| Local staging acceptance workflow exists | `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md` | The procedure is documented and current enough to use as staging guidance |
| VPS rollout kit exists | `ops/vps/README.md`, `ops/vps/*` | Host deployment pieces are present |
| Load budgets are defined | `ops/load/clinic_core.js`, `ops/load/endpoint_profiles.json` | Thresholds exist and are formalized |
| Tenant isolation baseline exists | `backend/app/core/tenant_scope.py`, `backend/app/middleware/tenant_scope_middleware.py`, `docs/architecture/INTEROPERABILITY_MULTI_CLINIC.md` | Implementation and architecture baseline are present |
| Observability guidance exists | `docs/runbooks/OBSERVABILITY_SLA_RUNBOOK.md`, `.github/workflows/monitoring.yml` | Monitoring intent is documented |

## Only described in docs/runbooks

| Area | What docs say | Why this is not enough |
|---|---|---|
| VPS staging promotion end-to-end | The VPS host rollout runbook describes the full promotion path | No live VPS execution proof is present in the current codebase |
| VPS deploy / soak / rollback | Scripts and runbooks describe deploy and rollback actions | No rehearsal evidence is included with the current `origin/main` |
| Health checks | `check_health.sh` defines health checks | A script existing is not the same as a passed production-like rehearsal |
| Observability SLA loop | Observability runbook defines metrics / alerts / review rhythm | No evidence of a completed SLA review loop on the promotion path |
| Multi-clinic isolation verification | Tenant scope docs define how isolation should work | No VPS promotion rehearsal proof is attached to the current baseline |

## Not confirmed at all

| Area | Missing proof |
|---|---|
| Production-like soak | No observed soak run on the VPS promotion path is present in current main |
| Rollback drill | No end-to-end rollback rehearsal evidence is present |
| Host-level failure recovery | No documented host failure recovery proof on a staging VPS |
| Alert response proof | No incident-style monitoring proof tied to promotion exists |
| Tenant isolation under promotion | No end-to-end promotion-host verification is present |

