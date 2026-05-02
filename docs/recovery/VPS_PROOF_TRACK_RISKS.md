# VPS Proof Track Risks

## Primary risks
- The staging host may expose a hidden env or service assumption that local proof does not catch.
- Rollback may require an operational step not captured in the runbook.
- Load tests may reveal a gap between published thresholds and actual promotion-path behavior.
- Observability may be configured but not actionable enough to support real promotion.
- Tenant isolation may be correct in code but still fail under a promotion-specific setup.

## Risk controls
- Keep the track proof-first and rehearsal-heavy.
- Require evidence after every meaningful action.
- Do not widen scope if a proof gap appears; document it and stop at the smallest missing capability.
- Prefer doc/runbook updates over code changes unless a rehearsal cannot proceed without a tiny guard or flag fix.

## Residual risk if the track succeeds
- Even with a successful rehearsal, there is still normal operational risk in the first real production promotion.
- That residual risk is acceptable only if the rehearsal evidence is complete and current.

