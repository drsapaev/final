# AI Factory Claims Missing From Current `origin/main`

> These are the significant gaps that current `origin/main` does not yet prove. They are intentionally limited to the most defensible items.

| Gap | Source doc(s) | Why current main does not prove it | Still valuable? | Best action |
|---|---|---|---|---|
| VPS staging promotion path completed end-to-end | `.ai-factory/ROADMAP.md`, `docs/runbooks/VPS_HOST_ROLLOUT_RUNBOOK.md` | The runbook exists, but the audit did not find evidence that the Linux VPS contour, deploy scripts, and EMR cutover were actually executed in current main | Yes | Dedicated recovery / rollout track |
| VPS deploy + soak + rollback proof | `docs/runbooks/VPS_HOST_ROLLOUT_RUNBOOK.md` | The runbook specifies deploy and verify steps, but current main does not itself prove the soak window / rollback boundary were exercised | Yes | Dedicated recovery / rollout track |
| Full load budget enforcement by critical profile | `.ai-factory/ROADMAP.md`, `docs/runbooks/LOAD_TESTING_RUNBOOK.md`, `.github/workflows/load-testing.yml` | Load testing exists, but the audit could not prove that every critical profile has a complete, enforced budget loop in the repo state | Yes | Add to future backlog |
| End-to-end observability SLA review loop | `.ai-factory/DESCRIPTION.md`, `docs/runbooks/OBSERVABILITY_SLA_RUNBOOK.md`, `docs/PRODUCTION_SECURITY.md` | Structured logging and metrics exist, but the audit did not find a single closed proof chain for all SLA alerts / review loops | Yes | Add to future backlog |
| Multi-clinic / tenant-isolation / interoperability story | `.ai-factory/ROADMAP.md` | The roadmap claims this milestone is completed, but the audit did not find enough explicit code evidence in current main to confirm the full isolation story | Maybe | Dedicated review track before any new work |

## Recommendation

- Do **not** open a broad new implementation track from these gaps unless VPS promotion is the active business priority.
- The safest immediate follow-up is a narrow ops track for VPS promotion only, or no new track at all if the current release train is stable.

