# Recovery Execution Order

## Stage 0 - Artifact Normalization
**Entry criteria**
- Existing recovery reports are present and readable.
- Current main is the only source of truth.

**Actions**
- Normalize branch names, statuses, and recommendation labels across the packet.
- Keep the recovery packet separate from main.

**Validation gates**
- Branch manifest, shortlist, docs disposition, execution order, and go/no-go all exist and agree with one another.
- No code changes have been made.

**Exit criteria**
- The packet is coherent and ready for review.

**Rollback rule**
- If a field is wrong, overwrite only the packet docs; do not touch main.

## Stage 1 - Docs Reconciliation Only
**Entry criteria**
- Packet review accepted.
- Current docs are categorized as keep current / historical evidence / update / archive.

**Actions**
- Update `docs/QUEUE_SYSTEM_ARCHITECTURE.md`.
- Archive the stale notification and online-queue architecture docs.
- Keep the active runbooks and panel QA docs aligned with current main.

**Validation gates**
- Link sanity and doc-path sanity.
- No runtime files are modified.

**Exit criteria**
- Docs disposition is resolved and reflects current main.

**Rollback rule**
- Restore only the last doc file if the category decision was wrong.

## Stage 2 - Lowest-Risk Maintenance Candidates
**Entry criteria**
- Docs are reconciled.
- Only the shortlist items are approved for execution.

**Actions**
- Process the 10 dependabot items one at a time.
- Cherry-pick only one ref before re-checking.

**Validation gates**
- Workflow syntax / CI dry run for GitHub Actions bumps.
- Targeted backend pytest / startup smoke for backend dependency bumps.

**Exit criteria**
- Every selected maintenance ref is either applied or explicitly deferred.

**Rollback rule**
- Revert only the last dependency bump if validation fails.

## Stage 3 - Narrow Manual Ports
**Entry criteria**
- A branch-specific gap is proven and not already covered by current main.
- The gap survived the shortlist filter.

**Actions**
- Port only the exact file slice, not the whole branch.
- Keep the port anchored to current main contracts.

**Validation gates**
- Targeted backend pytest or frontend vitest for the touched slice.
- Role-appropriate browser smoke if the slice affects a panel.

**Exit criteria**
- The narrow slice is green and lands cleanly.

**Rollback rule**
- Revert the single slice commit only.

## Stage 4 - Reimplementations From Current Main
**Entry criteria**
- The idea is still valuable but the branch is stale or too broad.
- Manual porting is not sufficient or not worth the risk.

**Actions**
- Rebuild the idea from current main, not from the historical branch tip.
- Keep the implementation small and contract-aware.

**Validation gates**
- Targeted tests first, then broader integration or smoke coverage.
- Contract parity with current main.

**Exit criteria**
- The reimplementation is green, documented, and aligned to current main.

**Rollback rule**
- Revert or feature-flag the new implementation if regressions appear.

## Stage 5 - Final Validation
**Entry criteria**
- All selected items are either recovered, reimplemented, or dropped.
- No unresolved doc classification remains.

**Actions**
- Cross-check the branch manifest, shortlist, docs disposition, and final verdict.
- Run the final regression gate for every touched area.

**Validation gates**
- Diff review is clean.
- Required tests are green.
- No new ambiguity remains in the packet.

**Exit criteria**
- The recovery packet is execution-ready for the next approved step.

**Rollback rule**
- No new changes in this stage; only evidence corrections if needed.
