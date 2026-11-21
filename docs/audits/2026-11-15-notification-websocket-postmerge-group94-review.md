# Continued independent Code Review — group94: review of open clinical start-visit fix PRs #4088 and #4087

**Review date:** 2026-11-15 (Asia/Tashkent). **Pinned main:** [`c9b3d72719a9f4edb84740b890cfd8063e86239d`](https://github.com/drsapaev/final/commit/c9b3d72719a9f4edb84740b890cfd8063e86239d). **Reviewed exact open fix heads:** [#4088 `cd418948146d4c7583a80a9ad4a86d827da8beab`](https://github.com/drsapaev/final/pull/4088), [#4087 `c6ccb1d25a49260913af74ea4ab9a824f8e3706c`](https://github.com/drsapaev/final/pull/4087). **Ongoing docs-only Draft audit:** [#4059](https://github.com/drsapaev/final/pull/4059). **Owner:** [#4063](https://github.com/drsapaev/final/issues/4063), 405 unique IDs, 76 checked, 329 unchecked at both initial/final review snapshots. No current-main source fixes merged during this group, no new finding IDs or per-ID status changes.

The independent reviewer read the latest root `AGENTS.md`, repository `.agents/skills/code-security/SKILL.md` and the race-condition rule, reviewed exact-head diffs, route handlers, queue ownership models, current main sibling doctor route and new integration tests. No local checkout was provided; no application test, PowerShell launcher, real patient DB or production action was performed.

## P1 — #4088 FAIL-OPEN gap for valid doctorless resource queues, same existing `REGSTART-BE-001` (do not add duplicate ID)

### Evidence

1. [`registrar_integration/_queue_ops.py:start_queue_visit` exact proposed branch](https://github.com/drsapaev/final/blob/cd418948146d4c7583a80a9ad4a86d827da8beab/backend/app/api/v1/endpoints/registrar_integration/_queue_ops.py#L639-L760) accepts `require_roles("Admin","Registrar","Doctor","cardio","cardiology","derma","dentist","Lab")`, looks up an arbitrary `OnlineQueueEntry` by global `entry_id`, and attempts to enforce non-Admin/Registrar ownership only under:
   ```python
   queue_specialist_id = getattr(entry_queue, "specialist_id", None)
   if queue_specialist_id:
       # compare caller Doctor to queue Doctor/normalized specialty; else 403
   ```
   When `queue_specialist_id is None`, **that whole authorization decision is skipped**. Execution continues into linked visit resolution then `queue_entry.status = "in_progress"`, `VisitLifecycleService.start_visit` for linked visits, and commits.
2. [`DailyQueue` source of truth](https://github.com/drsapaev/final/blob/c9b3d72719a9f4edb84740b890cfd8063e86239d/backend/app/models/online_queue.py#L113-L164) models queues with exactly **one** of doctor `specialist_id` **OR** `queue_resource_id`, enforced by `ck_daily_queues_owner_xor`; the latter intentionally has `specialist_id=NULL`. Lab/ECG service resource queues are legitimate, not malformed orphan records.
3. [Existing sibling `doctor_integration/_queue_ops.py:start_patient_visit` owner guard](https://github.com/drsapaev/final/blob/c9b3d72719a9f4edb84740b890cfd8063e86239d/backend/app/api/v1/endpoints/doctor_integration/_queue_ops.py) explicitly handles `if not doctor`/valid `queue_resource_id` and denies **non-Admin with 403** on that doctorless branch; this is the very owner policy #4088 purports to mirror.
4. [#4088 tests](https://github.com/drsapaev/final/blob/cd418948146d4c7583a80a9ad4a86d827da8beab/backend/tests/integration/test_start_visit_ownership_guards.py) create every `DailyQueue` with `_mk_queue(owner_doctor)` and `specialist_id=owner_doctor.id` in all five cases. They verify foreign doctor, owner, Registrar, same specialty and mismatched patient↔visit, but **none** attempts a resource queue with `specialist_id=None`. Therefore the reported 5/5 targeted and 262 neighboring tests do not establish guard completeness.
5. Risk: any authenticated `Doctor`/specialty/`Lab` role admitted by this legacy route can start a **different resource queue** and potentially its linked visit despite not possessing that queue's grant. This is a *source-proven branch reachability* in open proposed code, **not a reproduced real-clinic incident**. Severity P1 because clinical workflow/queue ownership, conditional on a reachable resource-owned queue.

### Required fix and tests

- Fail-first with synthetic `QueueResource(queue_tag="lab", active=True)`, a `DailyQueue(day=..., specialist_id=None, queue_resource_id=resource.id, queue_tag="lab", active=True)`, synthetic patient and linked open Visit, and called entry. Invoke `POST /api/v1/registrar/queue/{entry.id}/start-visit` as unrelated `Doctor`/specialty and `Lab` according to the service authorization policy. Require fail-closed `403`, unchanged queue + visit + audit, zero persisted state mutation; separately ensure Admin and Registrar still succeed for resource-owned queues. Do not break the five existing doctor-owned tests.
- If owner explicitly wants Lab to start their **own** lab resource, implement and test an actual resource-scoped Lab grant rather than the present implicit allow-all from `specialist_id=None`. The doctor-panel route presently enforces Admin-only on resource start; do not silently alter this policy in a different route without authorization.
- Retain the good newly added `DOCSTART-BE-001` patient↔visit `409` guard; it checks mismatch before visit mutation and its negative/positive test follows the intended contract.
- **Mandatory gate issue:** root [`AGENTS.md`](https://github.com/drsapaev/final/blob/c9b3d72719a9f4edb84740b890cfd8063e86239d/AGENTS.md) requires `ai/langgraph/scripts/run_agent_gate.ps1` for queue ownership and clinical lifecycle, with documented retry and approved narrow override. #4088 body reports **direct `agent_gate.py` `narrow_override`, `gate_misroute=true`**, not execution of the required launcher. Do not call this mandatory gate complete on the evidence provided. Require authorized proper gate execution or explicit recorded blocker; green CI/Agent Workflow Guards alone is distinct evidence.
- **Merge recommendation:** **BLOCK** treating #4088 as a complete fix for `REGSTART-BE-001` until this branch/test and mandated gate are addressed. [Detailed reviewer comment on #4088](https://github.com/drsapaev/final/pull/4088#issuecomment-6894087106) published directly. Leave owner `REGSTART-BE-001` unchecked.

## #4087 review — intended `DOCSTART-BE-002` loss-of-notes fix is mechanically narrow, not verified on main

- Exact [#4087 doctor start patch](https://github.com/drsapaev/final/blob/c6ccb1d25a49260913af74ea4ab9a824f8e3706c/backend/app/api/v1/endpoints/doctor_integration/_queue_ops.py#L823-L840) replaces unconditional `visit.notes="Прием начат в ..."` overwrite with `start_stamp` and `visit.notes=f"{visit.notes}\\n{start_stamp}" if visit.notes else start_stamp`. It leaves visit_time and transaction commit where they were. This **appears consistent with the narrow existing P2 `DOCSTART-BE-002` remediation intent**; no independent P1/P2 functional regression evidenced by this inspected diff.
- PR body claims an actual pre-fix RED and post-fix GREEN targeted integration plus 35/35 `test_doctor_general_queue.py`, and source patch shows an added `test_start_visit_preserves_pre_existing_visit_notes`; auditor did not execute those. Unit, backend, security and several reviewer gate status snapshots show successes, but some older review quality runs were failures: assess exact latest required-check state rather than cherry-picking a historic success.
- PR remains **OPEN/unmerged** on inspected head, so `DOCSTART-BE-002` correctly remains **unchecked** on owner issue #4063. Same mandatory gate concern: PR body explicitly says `run_agent_gate.ps1` **was not checked**; core clinical start is mandatory-gated under root AGENTS.md, even for a 6-line source change. Require compliant gate evidence/authorized exception before merge.
- No blanket green-light for production: checking exact source semantics/test code is not clinic staging acceptance.

## Current ledger and handoff

| Metric | Previous group93 | Group94 change | On review |
| --- | ---: | ---: | ---: |
| Owner unique IDs | 405 | +0 | **405** |
| Owner checked source fixes | 76 | +0 | **76** |
| Owner unchecked statuses | 329 | 0 | **329** |
| New independent ID candidates | — | 0 | **0** |
| Open fix-PR merge blockers discovered | — | **1** | `REGSTART-BE-001` doctorless-resource bypass in #4088 |
| New source PRs merged by auditor | — | 0 | 0 |

Next fixing agent: update #4088 with resource-owned authorization negative + positive tests before merge, then run mandatory queue/clinical gate, exact-head CI, and independently verify merged source before checking existing `REGSTART-BE-001`. If #4087 merges, require exact-head evidence and verify notes persistence on current main before ticking existing `DOCSTART-BE-002`. Post each fixing cycle in **this same Draft audit PR #4059** with SHAs, tests, gate and changed #4063 counts; no merge/docs checkbox can substitute for production-source fixes. `#4076` Telegram five blockers from group89 and `NOTIFYLIVEAUTH-BE-001` group92 residual remain separate. No source code, DB, patient data, gate, test runs, merge or production operations by this reviewer.
