# VPS Proof Track Evidence Requirements

## What must be proven first
1. A VPS staging deploy from the current host kit completes successfully.
2. The deployed host survives a soak run within the published load budgets.
3. Cutover and rollback both work in a controlled rehearsal.
4. Monitoring / observability is actually usable during the rehearsal.
5. Tenant isolation is preserved on the promotion path.

## What counts as enough evidence
- A deploy transcript with commands, timestamps, and service outcomes
- Health checks showing the app is reachable after deploy and after rollback
- k6 or equivalent load output mapped to the published thresholds
- Observability captures showing metrics, logs, and alert behavior
- Tenant-isolation scenario logs proving no cross-scope leakage
- A concise reviewer-facing proof note that points to the exact commands and outputs

## What can wait
- Cosmetic doc cleanups that do not affect proof clarity
- Any broad runtime refactor
- Any feature expansion unrelated to promotion readiness

## Evidence acceptance bar
- Evidence is acceptable only if it is specific to the VPS promotion path and not just a general local-development or historical acceptance artifact.

