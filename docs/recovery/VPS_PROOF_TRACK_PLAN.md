# VPS Promotion Proof Track Plan

## Purpose
- Convert the VPS readiness audit into a narrow, proof-first execution track.
- Prove the current `origin/main` is safe for VPS promotion without reopening historical recovery or broad runtime work.

## Scope
- In scope:
  - VPS staging deploy proof
  - cutover / rollback proof
  - load / soak proof against the published budgets
  - observability SLA proof loop
  - tenant-isolation verification on the promotion path
  - small doc clarifications needed to separate proof from historical evidence
- Out of scope:
  - broad feature development
  - EMR recovery
  - messaging/notifications recovery
  - any branch-recovery work
  - mainline code changes unrelated to promotion proof

## Track shape
- One narrow track: `VPS Promotion Proof Track`
- Maximum active items: 6
- Default preference: proof / rehearsal first, doc updates second, narrow implementation only if a proof run reveals a missing switch, script argument, or environment guard that blocks the rehearsal itself

## Success condition
- The track is successful only when the promotion path is proven with deploy, rollback, soak, observability, and isolation evidence that can be shown to a reviewer.

