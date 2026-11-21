# Group119 — independent review of parallel registrar remediation PR #4107

**Review date:** 2026-11-17. **Current main observed:** `933b1fe1fe83fc60ee6ab5825e775dec84abfd35` (merged password-reset PR #4077). **Reviewed implementation head:** `b3e21c31f5c0fc192273c177bd9e28399de0d954`, [PR #4107](https://github.com/drsapaev/final/pull/4107), open and unmerged. **Canonical owner:** [#4063](https://github.com/drsapaev/final/issues/4063). **Cumulative audit:** [Draft #4059](https://github.com/drsapaev/final/pull/4059).

**Mode/scope:** `direct_execute` for read-only source review, isolated synthetic expression evaluation, audit Markdown and GitHub comments. Allowed repository write: this audit document only on the existing audit branch. Application source, tests, CI configuration, policy, main, production and clinical data are denied write targets. No runtime repair or gate-policy change is made here. Root `AGENTS.md`, project `javascript-testing-patterns` and the installed React review skill were read. The mandatory application-change gate was not run and no gate pass is claimed.

## Evidence inspected and ownership

This pass reviews another agent's proposed implementation rather than counting historical fixes again. Inspected the PR patch, current head aggregation helper and new tests, actual `registrarWorklistRows.ts` consumer, status renderer, action predicates and backend-action availability helper. Checked that the relevant inline-action predicates also remain unchanged in current main. Formal merge status and implementation author were not inferred from a commit title.

Exact-head [Unified CI run 43859425051](https://github.com/drsapaev/final/actions/runs/43859425051) is completed/success. The same head has successful i18n, Agent Workflow, Regression Audit, Gitleaks, security and latest PR Review Quality results; a previous body-check run was cancelled and superseded. The PR description reports local RED/GREEN and gate success, but those are the implementation agent's claims, not execution personally performed by this reviewer. A successful existing suite does not prove the missing aggregate-to-renderer interaction.

## Disposition of the two existing IDs

| Existing ID | Review result | Accounting |
|---|---|---|
| `REGAGG-FE-001` | The branch removes FIO/phone/birth matching without canonical `patient_id`. Separate unknown records and same verified patient ID have explicit regression cases. No additional P1/P2 finding established for that bounded change. | Branch-level repair supported; **not merged into main and not credited**. |
| `REGAGG-FE-002` | The branch correctly gives differing statuses the honest `mixed` presentation marker, but fails to adapt its inline action consumers. One P2 regression below requires a change and interaction test. | **Changes requested; remains unchecked**. |

Do not create a duplicate global ID for this residual. Track it under `REGAGG-FE-002` / PR #4107 until independent acceptance.

## P2 — mixed aggregate suppresses valid inline cancellation and rescheduling

**Producer:** [`registrarAggregation.ts`](https://github.com/drsapaev/final/blob/b3e21c31f5c0fc192273c177bd9e28399de0d954/frontend/src/utils/registrarAggregation.ts#L620-L682) derives unique member statuses and sets the group `status` to `mixed` when they differ. A same-patient pair `pending + confirmed` therefore becomes `mixed`, in either order.

**Consumer:** [`appointmentsTableColumns.tsx:1360–1370`](https://github.com/drsapaev/final/blob/b3e21c31f5c0fc192273c177bd9e28399de0d954/frontend/src/components/tables/appointmentsTableColumns.tsx#L1360-L1370) still computes:

```text
canCancel     = !isDoctorView && status in {waiting, called, pending, confirmed}
canReschedule = !isDoctorView && status in {waiting, pending, confirmed}
```

Both `pending` and `confirmed` individually pass both gates. Their new aggregate `mixed` passes neither. The rendering branches consequently omit both inline buttons. `waiting + confirmed` produces the same regression. Before this PR, either member's first-row status retained both controls. The relevant predicates remain present on [current main](https://github.com/drsapaev/final/blob/933b1fe1fe83fc60ee6ab5825e775dec84abfd35/frontend/src/components/tables/appointmentsTableColumns.tsx#L1348-L1358), so this is not a branch-only concern already repaired in main.

**Affected scope:** the all-departments aggregate's inline actions. Switching to a departmental row or another menu may remain a workaround; this review does **not** claim that every cancellation/rescheduling route is disabled. It does not claim that an unauthorized backend mutation occurs. The regression is the loss of previously available user controls for a group whose members can still be eligible.

### Executed evidence and its limits

Executed a standalone Node **v22.16.0** script using the exact status-finalization expression and the two predicates copied from the reviewed head. Synthetic inputs only:

| Member statuses | Before change: first member status | New aggregate | Old inline controls applied to new aggregate |
|---|---|---|---|
| pending, confirmed | cancel=true, reschedule=true | mixed | cancel=false, reschedule=false |
| confirmed, pending | cancel=true, reschedule=true | mixed | cancel=false, reschedule=false |
| waiting, confirmed | cancel=true, reschedule=true | mixed | cancel=false, reschedule=false |

The expression check passed assertions establishing these three regressions. **It was not a checkout of the full app, a rendered React test, Vitest, Playwright, an API call or a production reproduction.** The seven new tests in [`registrarAggregation.test.ts`](https://github.com/drsapaev/final/blob/b3e21c31f5c0fc192273c177bd9e28399de0d954/frontend/src/utils/__tests__/registrarAggregation.test.ts#L831-L935) inspect aggregate return values and do not exercise the action renderer, explaining why green CI can coexist with this source-confirmed mismatch.

### Fixing-agent instructions — continue in the same PR

1. Keep the identity repair and honest `mixed` badge. Do not restore demographic identity guessing.
2. Derive aggregate action availability from canonical per-record capabilities and provide an explicit eligible target selection. **Do not turn `mixed` into `waiting`, and do not send an operation to every record merely because one is eligible.** Terminal/ineligible records and backend permissions remain authoritative.
3. Add an interaction test that combines the real aggregation output with the table/action renderer, instead of adding another pure return-value assertion. Required cases: pending+confirmed and reverse order; waiting+confirmed; done+waiting; denied capabilities; uniform-status control. Assert controls are reachable where appropriate, the intended canonical record refs are selected, and ineligible members receive no command.
4. Run focused aggregation/renderer/action tests, the actual mandatory project gate for the reviewed source scope, and final-head CI. Record command, head SHA, result and sanitized evidence. No inferred gate pass, no merge before this regression is resolved.

A direct [review comment with the handoff](https://github.com/drsapaev/final/pull/4107#issuecomment-6953046651) was posted on the implementing agent's PR. This is a requested change in the review comment, not a claim that a formal GitHub `REQUEST_CHANGES` review was submitted.

## Existing source PR #4106 and tracker

[#4106](https://github.com/drsapaev/final/pull/4106) remains an open Draft at head `17fba86e2c9fe3ed5505bae133478327b39c2dbb`. Its description still records the missing actual PowerShell launcher evidence. This pass did not modify or resynchronize its branch and did not approve merge. Do not repeat older claims that it is synchronized to the newly advanced main without a fresh ancestry comparison.

At this pass's owner read, #4063 reports **536 historical IDs, 156 verified and 380 awaiting adjudication**. **Group119 adds zero fixed credits, zero duplicate IDs and changes no existing checkbox.** The result is one identified integration regression in an open parallel-agent PR, with concrete repair instructions before merge. No application code, main merge, deployment, feature flag or patient record was changed by this reviewer.
