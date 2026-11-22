# Group111 — Cardiology completion ACK identity and medical AI review follow-up

**Date:** 2026-11-16. **Current main pinned:** [d7eb9729248f949af5c74b45f1fdf26b914835fe](https://github.com/drsapaev/final/commit/d7eb9729248f949af5c74b45f1fdf26b914835fe). **Owner:** [#4063](https://github.com/drsapaev/final/issues/4063). **Cumulative audit:** [Draft PR #4059](https://github.com/drsapaev/final/pull/4059). **Source repair proposed, NOT MERGED:** [Draft PR #4106](https://github.com/drsapaev/final/pull/4106), final reviewed head `c517b12b2f81eaf8b2ab355f9b3f60e8287f48d1`. **AI guard repair proposed, NOT MERGED:** [Draft #4105](https://github.com/drsapaev/final/pull/4105), head `320198e347ff4596fdb5eb24cb3d660fd78f43c6`.

## Confirmed current-main weakness: `DOCFLOW-FE-004` (P1/P2 provenance, stale unsuccessful reply P2)

The Group110 report left [original #3902 inline comment](https://github.com/drsapaev/final/pull/3902#discussion_r4501222490) open because merged [#3915](https://github.com/drsapaev/final/pull/3915) had source guards but only a source-string test. A deeper source inspection now confirms a **distinct residual even with that guard**:

- [`CardiologistPanelUnified.tsx` on main](https://github.com/drsapaev/final/blob/d7eb9729248f949af5c74b45f1fdf26b914835fe/frontend/src/pages/CardiologistPanelUnified.tsx#L1475-L1548) sends `await queueService.completeVisit`, tests `completionAck?.success !== true` **before** the live `selectedPatientRef.current` identity guard. If clinician switched from A to B while A's command was pending, old A's rejected/ambiguous 2xx body emits an error and ambiguous ACK can initiate a background queue refresh in B's context. A successful stale A reply *does* reach the subsequent guard and is dropped.
- The surrounding `catch` also handles a rejected transport promise by issuing `notify.error` without checking the patient's current selection. Hence old A network failures can be displayed against B. Server may already have committed A before the browser received any response: this is **client feedback/context ownership**, not a claim server state can be rolled back or blind retries are safe.
- The original `finally` unconditionally releases the shared `loading` flag. Making that cleanup contingent only on A's identity would **create a sticky busy state for B**; the narrowly scoped repair intentionally **preserves** the existing unconditional cleanup, and the new tests check B becomes usable once A finishes. A separate token for multiple overlapping completion requests might later be appropriate; not proven/tested here and not included in this change.

## Draft implementation [#4106](https://github.com/drsapaev/final/pull/4106)

**Scope:** two paths only. `frontend/src/pages/CardiologistPanelUnified.tsx` moves the already-present post-POST patient+queue-entry guard immediately before any ACK classification (success/rejected/unknown), and adds an identical captured-identity check in the transport-error `catch`, suppressing an obsolete A toast. The `finally` retains unconditional `setLoading(false)` so the new patient's controls do not stick busy. All canonical queue and visit lifecycle rules stay on backend. No queue service, EMR persistence, security, payment, router or schema changes.

**Synthetic behavioral tests staged first:** [`CardiologistPanel.deferredCompletion.test.tsx`](https://github.com/drsapaev/final/blob/c517b12b2f81eaf8b2ab355f9b3f60e8287f48d1/frontend/src/pages/__tests__/CardiologistPanel.deferredCompletion.test.tsx). Uses the **real `CardiologistPanelUnified` handler** with mocked shared navigation hook and presentational `VisitTab`, not a source-text regex. It holds A's command while committing B selection, then releases:
1. `success:true`: no stale A success toast, no B deselect/tab reset, no auto-call.
2. `success:false`: no stale A rejection toast in B, no B reset/call.
3. `success:false,unknown:true`: no stale error, no incorrect queue reconciliation in B, no B reset/call.
4. Rejected transport promise: no stale A network-error toast in B, B remains selected.
5. Positive current-A `success:true`: confirms old valid successful completion path still clears A and calls next.
Stale cases also check B's inherited loading flag clears when A settles. All fixtures use synthetic patient/visit identifiers, no PHI.

**Verification status:** PR Review Quality Body Gate completed successful on early drafts; later new-head CI was queued/pending when this report was prepared. **No Vitest, local TS/ESLint, browser, git diff check, staging, mandatory `ai/langgraph/scripts/run_agent_gate.ps1`, or full CI was personally executed**. The test is a proposal, NOT executed RED→GREEN evidence. Follow latest **head `c517b12b2...`** check statuses; earlier running heads are superseded. **KEEP DRAFT; no merge or deployment**. Retain [ ] `DOCFLOW-FE-004` in owner until current-head tests, gate, CI, independent review and merged-main source verification.

## Existing dermatology AI Draft [#4105](https://github.com/drsapaev/final/pull/4105)

**Exact-head Unified CI finally completed SUCCESS** on `320198e347ff4596fdb5eb24cb3d660fd78f43c6`, as did PR Review Quality, i18n, Agent Workflow Guards, Regression Audit, Gitleaks and security scanning. Its two-file fail-closed patch checks **root-level** `AIResponse` fields for explicit success, nonempty suggestion and advisory metadata before displaying clinical AI text.

**Merge barriers remain despite successful CI:** (i) AI-authored `run_agent_gate.ps1` not actually executed; (ii) root [`AGENTS.md`](https://github.com/drsapaev/final/blob/d7eb9729248f949af5c74b45f1fdf26b914835fe/AGENTS.md) requires `ai_safety_meta.requires_doctor_confirmation` nested for every medical AI response, and specifies P0 action if absent, while this `POST /ai/v2/analyze-skin-file` endpoint [`AIResponse`](https://github.com/drsapaev/final/blob/d7eb9729248f949af5c74b45f1fdf26b914835fe/backend/app/services/ai/ai_interfaces.py#L42-L75) and [skin-photo test](https://github.com/drsapaev/final/blob/d7eb9729248f949af5c74b45f1fdf26b914835fe/backend/tests/test_ai_analyze_skin_file.py) require **root-level** safety fields. Only authorized domain owner/safety review can reconcile policy and triage whether an actual incident/flag action is warranted. This auditor did not validate production response or perform production incident actions. Retain [ ] `DERMAAI-FE-002` until proper proof.

## Owner accounting

At start of Group111: **536 unique IDs / 144 verified / 392 awaiting adjudication** after Group110's six historical source+test+CI credits. No checkbox is changed by Group111. Both currently open Draft PRs require actual validation and appropriate gate; successful CI alone is not substitute. The [#4103 process-gate conflict](https://github.com/drsapaev/final/pull/4103#issuecomment-6914552632) remains historical: a merged fix with credited functional evidence does not prove the mandated PowerShell wrapper was run *before* merge.

**Next action:** execute failing/green focused tests for #4106 from a verified checkout, address head-specific CI findings, run the canonical PowerShell wrapper and record SHA+exit+sanitized handoff; independent reviewer may then credit the fix after actual merge. Separately reconcile the AI safety envelope for #4105 without changing a live feature flag on conjecture.
