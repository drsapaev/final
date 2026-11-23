# Continued independent Code Review — group96: pending #4091 terminal-state guard and #4087 rebase

**Date:** 2026-11-15, Asia/Tashkent. **Pinned current main:** [`3dbb6f95c25f8dd3e9e6a0c1c96520b4e77ae4a8`](https://github.com/drsapaev/final/commit/3dbb6f95c25f8dd3e9e6a0c1c96520b4e77ae4a8) (unchanged from group95). **Same continuing Draft audit:** [#4059](https://github.com/drsapaev/final/pull/4059), groups47–95 retained. **Owner [#4063](https://github.com/drsapaev/final/issues/4063):** 405 unique IDs / **77 checked / 328 unchecked**, current at review. Exact heads examined: [#4091 `9ab7f0bb06d890a92a556a0b29e985c88f6611ee`](https://github.com/drsapaev/final/pull/4091), [#4087 `4e27facc8fea3fe621222a511f3764d4fdc4fe7a`](https://github.com/drsapaev/final/pull/4087), and stale [#4089 `016984dc0c68c681201afc4cdf4dc2a45402f0eb`](https://github.com/drsapaev/final/pull/4089). No app source edits, project tests or PowerShell gate run by reviewer; only independent static review, verification of PR workflow results, and docs/comments.

Read root `AGENTS.md`, repo security skill `.agents/skills/code-security/SKILL.md`, real exact #4091 source and tests, existing registrar action helper, doctor action helper, online queue service terminal alias contract and original audit group24. No patient data, provider calls, staging, source merge, or production activity.

## Existing P1/P2 `REGSTART-BE-002` — #4091 partially improves terminal guard but still fails closed poorly for other states

**Proposed source:** [`backend/app/api/v1/endpoints/registrar_integration/_queue_ops.py`](https://github.com/drsapaev/final/blob/9ab7f0bb06d890a92a556a0b29e985c88f6611ee/backend/app/api/v1/endpoints/registrar_integration/_queue_ops.py#L718-L771).

The open PR adds:

```python
if queue_entry.status in ("cancelled", "no_show", "served"):
    raise HTTPException(status_code=409, detail=...)
queue_entry.status = "in_progress"
```

This is a genuine safeguard for **those three literal values**, and the [new regression test](https://github.com/drsapaev/final/blob/9ab7f0bb06d890a92a556a0b29e985c88f6611ee/backend/tests/integration/test_registrar_all_appointments.py#L921-L1000) confirms via author test/CI that each can no longer restart; existing `waiting` positive control preserved. However *every other persisted value* passes, including documented non-startable terminal or already-in-progress values, and unlinked queue entries have no subsequent Visit lifecycle validation before commit.

**Concrete supported alternatives:**

- [`REGISTRAR_CANCEL_BLOCKED_STATUSES`](https://github.com/drsapaev/final/blob/3dbb6f95c25f8dd3e9e6a0c1c96520b4e77ae4a8/backend/app/api/v1/endpoints/registrar_integration/_helpers.py#L77-L111) includes `canceled`, `cancelled`, `completed`, `done`, `served` as canceled/completed variants. Only `cancelled` and `served` are denied here. This same helper defines `REGISTRAR_START_STATUSES={"waiting","queued"}` for the registrar's permitted action.
- [`online_queue_new_service.py`](https://github.com/drsapaev/final/blob/3dbb6f95c25f8dd3e9e6a0c1c96520b4e77ae4a8/backend/app/services/online_queue_new_service.py#L24-L45) explicitly accepts both `canceled` AND `cancelled` as *terminal cancellation spellings* and classifies `incomplete` as consumed.
- [Doctor-panel `_doctor_queue_available_actions`](https://github.com/drsapaev/final/blob/3dbb6f95c25f8dd3e9e6a0c1c96520b4e77ae4a8/backend/app/api/v1/endpoints/doctor_integration/_helpers.py#L128-L161) grants `start_visit` only for `called`; no second start for `in_progress` or `diagnostics`, and the real queue model documents `incomplete` among states.
- `OnlineQueueEntry.status` is a `String(20)` column, without status CHECK on the inspected model. Legacy/alias values can remain in persisted data. A real `canceled` alias is supported by the canonical service and is a high-value negative control.

A legitimate Registrar can therefore submit an **unlinked** entry with e.g. `status="canceled"`, `"completed"`, `"done"`, `"incomplete"`, `"diagnostics"`, or already `"in_progress"`. These avoid the three-value denylist and directly overwrite the queue status to `in_progress` with HTTP 200, potentially resurrecting completed/canceled workflows or allowing repeated start; original group24 [`REGSTART-BE-002`](https://github.com/drsapaev/final/pull/3892#issuecomment-6732140744) describes this exact uncontrolled prior-state transition root cause. **This is an existing ID, not a new P1/P2 finding ID.** No live clinic request was performed; static branch reachability is clear and source-backed.

**Source review recommendation:** **BLOCK merging #4091 as a complete `REGSTART-BE-002` fix** pending a policy-approved positive allowlist of startable states (preserve existing registrar direct-start `waiting`, include `queued` if intended by action SSOT, and `called` if legitimately supported) and 409 rejection for every other state including unknowns. Add fail-first parameterized integration tests with **no linked Visit** for `canceled,cancelled,no_show,served,completed,done,incomplete,diagnostics,in_progress` and a random illegal value, asserting 409 and no mutation, plus positive controls. Do **not** silently restrict documented operator `waiting` workflow. The original auditor explicitly suggested allowed-state guard; reject list completeness is not proven by a successful targeted 4-case test. `QRSTATUS-BE-001` concurrency remains separate and unchecked, as do resource-owner security findings; don't add duplicate IDs.

**Direct source-backed PR comment already posted:** [#4091 comment 6898947794](https://github.com/drsapaev/final/pull/4091#issuecomment-6898947794).

**CI/gate:** #4091 at reviewed SHA has a current **Unified CI SUCCESS**, Security Scan SUCCESS, Gitleaks SUCCESS, Agent Workflow Guards SUCCESS, PR Review Quality Gate latest SUCCESS (older run failed but was followed by green). None of them tests omitted alternate terminal states. PR description expressly states `run_agent_gate.ps1` **not checked**, despite mandatory launcher [`AGENTS.md`](https://github.com/drsapaev/final/blob/3dbb6f95c25f8dd3e9e6a0c1c96520b4e77ae4a8/AGENTS.md) for clinical lifecycle/queue policy; obtain launcher or authorized exception before merge. Do not confuse the passing Agent Workflow Guards CI job with actual runner execution.

## Other relevant open PR reconciliation

- [#4087 latest head `4e27facc8fea3fe621222a511f3764d4fdc4fe7a`](https://github.com/drsapaev/final/pull/4087) has been **rebased/synchronized** after #4088 merged. Exact current diff still consists of the narrow doctor start notes preservation:
  ```python
  start_stamp = f"Прием начат в {clinic_now.strftime('%H:%M')}"
  visit.notes = f"{visit.notes}\\n{start_stamp}" if visit.notes else start_stamp
  ```
  plus its synthetic integration test. This is a mechanically sound candidate for existing `DOCSTART-BE-002` P2 with no new P1/P2 issue detected in scoped changed source. New head's Unified CI, PR Quality Gate, Security Scan, Gitleaks and Agent Workflow Guards report SUCCESS. Nevertheless #4087 remains **OPEN** and body still says the mandatory `run_agent_gate.ps1` was not checked; keep `DOCSTART-BE-002` unchecked until merged and independently verified under project gate policy. Previous auditor comment: [#4087 group94](https://github.com/drsapaev/final/pull/4087#issuecomment-6894117869).
- [#4089](https://github.com/drsapaev/final/pull/4089) remains open on identical head from group95, with the two **actual CI failures** (backend tests contaminated by test helper mocking; PR Review Quality Gate missing Negative auth proof). Do not repeat IDs: [detailed group95 CI proof](https://github.com/drsapaev/final/blob/0461132b2ec665ef191a1004513fda84c3a2ea16/docs/audits/2026-11-15-notification-websocket-postmerge-group95-review.md) and [direct fix PR comment](https://github.com/drsapaev/final/pull/4089#issuecomment-6896992621).
- The once erroneously checked [`REGSTART-BE-001`](https://github.com/drsapaev/final/issues/4063) still has resource-queue non-owner bypass in merged #4088 (group95), now correctly unchecked. Distinct `DOCSTART-BE-001` stays checked.

## Ledger / next steps

| Metric | Group95 | Group96 delta | Snapshot |
| --- | ---: | ---: | ---: |
| Total unique IDs | 405 | +0 | **405** |
| Checked `FIXED_VERIFIED_ON_MAIN` | 77 | 0 | **77** |
| Unchecked owner IDs | 328 | 0 | **328** |
| New unique finding IDs | — | **0** | — |
| New source fix merges by independent reviewer | — | **0** | — |

Priority 1: fixing agent updates #4091 with **positive allowed-status policy**, a full set of alternative terminal regressions and mandatory queue/clinical launcher evidence before merge. Priority 2: #4089 test fixture isolation + PR Quality Gate; then exact-head full CI. Priority 3: #4087 verified merge when authorized. Publish **each fixing step and owner count delta** in SAME Draft audit #4059, **never** tick a source ID on merely opening a PR, from a green test for an incomplete branch, or from docs-only audit merge. No app runtime tests or protected source changes were made in this independent review.
