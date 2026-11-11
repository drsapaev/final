# Consolidated independent post-merge Code Review — PR #3969–#3996

**Date:** 2026-11-11 (Asia/Tashkent). **Repo:** `drsapaev/final`. **Census cut-off:** main head `440ec010aa` (merge commit of #3996, 2026-11-10T22:27:45Z) — the latest merged PR at review time. **Purpose:** documentation-only retrospective in a new dedicated PR; **NOT** a repair PR, exhaustive clinical acceptance or merge/deployment authorization.

## Executive summary

- PR numbers **#3969–#3996** contain **10 merged PRs** (all authored by `drsapaev`): #3969, #3970, #3971, #3972, #3986, #3988, #3992, #3994, #3995, #3996. **No PR in this interval was closed-unmerged** (#3987 and #3989 — earlier iterations of the #3986/#3988 fixes — were closed in favour of their successors before this census window). Open drafts (#3973–#3993 wave, #3958, #3961, #3968) do **not** enter the merged-remediation count.
- **All 10 merged PRs have zero recorded formal GitHub pull-request Reviews** at the audit snapshot, and the **PR Review Quality Gate failed at the exact heads of #3970 (×2), #3972 and #3988** before those merges. This records the absence of formal review submissions; it does not itself prove the implementations defective.
- **The current `main` head is RED**: the Unified pipeline's *Generated API types freshness* step fails on `440ec010aa` (push run [42914777992](https://github.com/drsapaev/final/actions/runs/42914777992)); it had already failed at #3996's head `110f46a459` (run [42913774625](https://github.com/drsapaev/final/actions/runs/42913774625)) before the merge. See **RETRO-3996-01 (P1)**.
- **Two source-backed residual findings** (fail-first reproducible): **P1 × 1, P2 × 1**. No confirmed P0. Fix PRs opened from this review: [#3998](https://github.com/drsapaev/final/pull/3998) (RETRO-3996-01) and [#3999](https://github.com/drsapaev/final/pull/3999) (RETRO-3995-01), both with fail-first regression evidence.
- **Ledger reconciliation:** audit-ledger **#3886 (120 findings) is closed at 120/120** (round 24 #3963 → round 30 #3994, which explicitly closes the ledger); **#3892 (27 findings, dental/dermatology) is closed at 27/27** (#3903/#3908 + follow-ups #3966/#3986); every RETRO from post-merge reviews **#3958** (RETRO-3947-01 → #3959; RETRO-3953-01 → #3992; RETRO-3953-02/03/04 → #3995) and **#3968** (RETRO-3963-01 → #3969; RETRO-3960-01 → #3988; RETRO-3965-01 → #3972; RETRO-3966-01 → #3986) has a merged fix.
- The **draft** ledger **#3961** (queue-position / WebSocket / notifications, 50 findings) is outside this review's range and actively processed by the owner (round 29 = #3996 merged; open drafts #3973–#3993). This audit deliberately does not duplicate that work.

## Findings — source-backed, fail-first reproduced

### RETRO-3996-01 — P1 — main is red: openapi.json changed without regenerating the frontend API types

**Origin:** [#3996](https://github.com/drsapaev/final/pull/3996). **Sources:** `backend/openapi.json` (stats endpoint description changed), `frontend/src/types/generated/api.ts` (NOT regenerated), CI job logs of runs [42913774625](https://github.com/drsapaev/final/actions/runs/42913774625) (PR head `110f46a459`) and [42914777992](https://github.com/drsapaev/final/actions/runs/42914777992) (main head `440ec010aa`).

PR #3996 (QPOSAUTH-BE-001/002) edited `backend/openapi.json` — appending `Доступно: Admin, Registrar, Doctor (и SuperAdmin).` to the queue-position stats endpoint description — but did not run `npm run generate:api-types`. The Unified pipeline's freshness guard (`generate:api-types:check` → `git diff --exit-code src/types/generated/`) therefore fails with `API types are out of date! Run: npm run generate:api-types` **on the current main head**, so every subsequent push to main inherits a red Unified pipeline and the freshness invariant (Phase 0.5 of the JS-to-TS migration plan) is broken. The failure was visible at the PR head before merging (pull_request run 42913774625, job `Frontend lint`, failed step `🔒 Generated API types freshness`) and was merged anyway.

**Impact:** CI/process integrity, not clinical behavior (the generated diff is JSDoc comment-only). But a red main masks future real failures in the same pipeline and blocks the freshness invariant for any later backend change.

**Fix:** [#3998](https://github.com/drsapaev/final/pull/3998) — the mechanical regeneration through the repo's own pipeline (`scripts/generate-api-types.sh`, openapi-typescript 7.13.0): exactly the two JSDoc description lines for `get_queue_positions_stats…`, no other drift, no hand edits.

### RETRO-3995-01 — P2 — a mutation completing after a context switch repaints the previous diagnosis's phrases under the new one

**Origin:** [#3995](https://github.com/drsapaev/final/pull/3995) (the current hook contract; the pattern predates it, but #3992/#3995 established the context-transition honesty contract this path violates). **Sources:** [`frontend/src/hooks/useDoctorSectionTemplates.ts`](https://github.com/drsapaev/final/blob/440ec010aa38d1e1648e3beb4ca00f649d09286c/frontend/src/hooks/useDoctorSectionTemplates.ts) — `updateTemplate`/`pinTemplate`/`unpinTemplate`/`deleteTemplate` call their closure-captured `fetchTemplates(true)`; commit guards key only on `epoch === requestEpochRef.current`.

Reproducible interleaving (fail-first reproduced in [#3999](https://github.com/drsapaev/final/pull/3999)'s suite): the doctor edits an I10 phrase (PUT in flight) → switches the diagnosis to I20 → the I20 effect fetch takes epoch E2 → the PUT resolves and the captured **I10** forced refresh takes epoch E3 — now the newest — so E2's I20 response is discarded by the epoch guard (and never cached), while E3's **I10** response commits `setTemplates(I10 phrases)` under the live I20 context. The render-time context gate (RETRO-3953-02) cannot repair this: no further context change occurs. The phrases are personal clinical phrases and are actionable (Apply inserts their text into the EMR field), so the previous diagnosis's suggestions stay rendered and actionable under the new diagnosis — exactly what RETRO-3953-02 promised to prevent, through the mutation path neither #3992 nor #3995 covered.

**Impact:** wrong-context clinical suggestions presented as actionable (same doctor, same screen — no cross-principal leak; the module cache stays owner-scoped). No backend write occurs through this path.

**Fix:** [#3999](https://github.com/drsapaev/final/pull/3999) — (1) `liveFetchRef` latest-ref: all four mutations refresh the LIVE context; (2) `liveCacheKeyRef` defense in depth: every state commit (cached hit, fresh load, error branch, shared-promise join) additionally requires the request's `cacheKey` to still be the hook's live `cacheKey`. RED 3/3 on pre-fix source, GREEN 3/3 with the fix; existing suites unchanged (principalSwap 3/3, consistency 4/4, cache + phrases.invalidation 11/11).

## Full merged inventory and exact-head CI records

| PR | Scope | Changed files | Exact-head runs (success/total, non-green) | Verdict |
| --- | --- | ---: | --- | --- |
| [#3969](https://github.com/drsapaev/final/pull/3969) | RETRO-3963-01: every authoritative selection invalidates pending navigation intents | 3 (+313/−4) | 9/10 (skipped: dependabot auto-merge) | No new confirmed finding in this bounded read; epoch protocol now covers all entry paths incl. unmount and URL-hydration live-selection guard |
| [#3970](https://github.com/drsapaev/final/pull/3970) | CARDAI-FE-001/002, CARDSVC-FE-001/002, CARDHIST-FE-001 (round 28) | 16 (+913/−82) | 11/14 (**PR Review Quality Gate ×2 failure**; skipped: dependabot) | No new confirmed finding; honest no-context AI state, versioned transport, read-only catalog, reserved-window preview helper all verified against current main |
| [#3971](https://github.com/drsapaev/final/pull/3971) | EMRAUTOSAVE-FE-001, EMRTREAT-FE-001, EMRLEARN-FE-001 (round 29) | 8 (+434/−19) | 9/10 (skipped: dependabot) | No new confirmed finding; conflict bookkeeping precedes success stamps, canonical treatment selector mirrors `get_emr_text_field`, canonical ICD learning verified |
| [#3972](https://github.com/drsapaev/final/pull/3972) | RETRO-3965-01: P-axis never relabeled as QRS axis | 2 (+104/−7) | 10/12 (**PR Review Quality Gate failure**) | No new confirmed finding; `axis`=qrsAxis-only with explicit null, `pAxis` kept separate; viewer persists null structured axis |
| [#3986](https://github.com/drsapaev/final/pull/3986) | RETRO-3966-01: locked records open an inspection-only ToothModal | 13 (+357/−13) | 9/10 (skipped: dependabot) | No new confirmed finding; also repaired two pre-existing CI flakes (EMRHistoryPanel.identity waitFor race; RescheduleSlots hardcoded date vs Asia/Tashkent SSOT, run 42880576300) — positive evidence |
| [#3988](https://github.com/drsapaev/final/pull/3988) | RETRO-3960-01: changed confirmation channel is a different intent | 2 (+131/−3) | 9/11 (**PR Review Quality Gate failure**) | No new confirmed finding; channel is part of intent equality; replay always reports the persisted channel |
| [#3992](https://github.com/drsapaev/final/pull/3992) | RETRO-3953-01: principal swap drops previous doctor's phrases synchronously | 2 (+206/−1) | 9/10 (skipped: dependabot) | No new confirmed finding; owner check also gates cache repopulation |
| [#3994](https://github.com/drsapaev/final/pull/3994) | EMRKEY-FE-001, EMRSTATUS-FE-001 (round 30 — **closes ledger #3886 at 120/120**) | 4 (+290/−22) | 9/10 (skipped: dependabot) | No new confirmed finding; native undo stays with the browser inside editables, amended records show signed provenance |
| [#3995](https://github.com/drsapaev/final/pull/3995) | RETRO-3953-02/03/04: context transitions, forced refresh, shared-GET honesty | 2 (+287/−24) | 9/10 (skipped: dependabot) | **RETRO-3995-01 (P2)** — the mutation path violates the context-transition contract (see finding) |
| [#3996](https://github.com/drsapaev/final/pull/3996) | QPOSAUTH-BE-001/002 (audit #3961 round 29): stats endpoint staff-only, unlinked entries fail closed | 3 (+277/−14) | 8/10 (**Unified pipeline failure — API types freshness**, at head AND on main push 42914777992) | **RETRO-3996-01 (P1)** — main is red (see finding) |

## Open PRs (excluded from post-merge conclusions)

| PR | State and context |
| --- | --- |
| #3958 | Draft docs-only consolidated review #3945–#3957; its four RETROs are now all fixed (#3959, #3992, #3995) |
| #3961 | Draft docs-only queue-position/WebSocket/notifications audit (50 findings); owner's active fix queue (round 29 = #3996 merged; drafts #3973–#3993 open) — separate review needed |
| #3968 | Draft docs-only consolidated review #3959–#3967; its four RETROs are now all fixed (#3969, #3988, #3972, #3986) |
| #3973–#3993 | Open drafts: telegram webhook origin, notifications WebSocket series (#3974–#3980), queue-ws series (#3981–#3984, #3990, #3991, #3993), AI-PR merge-gate policy (#3975), Palette/UX and dependabot PRs — outside this review's range |

## Reconciliation with previous consolidated reviews

- **#3968** documented RETRO-3963-01 (P1), RETRO-3960-01, RETRO-3965-01, RETRO-3966-01 (P2 ×3). **All four are now fixed and merged**: #3969, #3988, #3972, #3986 respectively. Status: `FIX_PRESENT_SOURCE / FAIL-FIRST-SUITES-MERGED`.
- **#3958** documented RETRO-3947-01 (fixed by #3959, historical) and RETRO-3953-01/02/03/04. **All fixed**: #3992 (P1) and #3995 (P2 ×3). Status: `FIX_PRESENT_SOURCE / FAIL-FIRST-SUITES-MERGED`.
- **Ledger #3886** (120 findings, merged 2026-11-06): rounds 24–30 (#3963, #3965, #3966, #3967, #3970, #3971, #3994) closed the remaining findings; #3994's body explicitly declares **120/120 closed**. Independent verification during this census: every finding ID of the ledger has a merged fix PR referencing it.
- **Ledger #3892** (27 findings, dental/dermatology, merged 2026-11-06): all 27 fixed by #3903/#3908 (2026-11-07) with follow-ups #3966 and #3986. Verified by per-ID search during this census.
- Passing suites do not cover newly identified negative interleavings; this report preserves the positive evidence of the ten merges while recording the two residuals above.

## Follow-up order and acceptance gates

1. **P1 main-red freshness** ([#3998](https://github.com/drsapaev/final/pull/3998)): merge only after the Unified pipeline is green again on the PR head (the freshness step must pass); the fix is the repo's own regeneration pipeline, no hand edits.
2. **P2 cross-context phrases** ([#3999](https://github.com/drsapaev/final/pull/3999)): fail-first suite included (RED on pre-fix source); require the existing principalSwap/consistency suites to stay green; independent code review on the final SHA per the AGENTS.md gate for EMR-adjacent changes.
3. The **PR Review Quality Gate failures at the exact heads of #3970/#3972/#3988** (formal review submissions) remain a process debt consistent with #3968's observation; the owner's draft policy #3975 proposes a verified gate before merging AI-authored PRs — this audit does not take a position on it.
4. Carry the two new finding IDs into the audit ledger with status `SOURCE-CONFIRMED / FAIL-FIRST-REPRODUCED / FIX-PENDING-MERGE`; do not mark them fixed until the fix PRs are merged with their suites green on exact heads.

## Scope, validation and rollback

- **Execution mode:** `direct_execute` for **one documentation-only retrospective file** plus two narrowly scoped fix branches opened from this review (#3998, #3999), each with its own cyclic evidence in the PR body. This dossier does not modify clinical business rules or deployment policy.
- **First-touch / allowed path:** `docs/audits/2026-11-11-postmerge-code-review-3969-3996.md` only (this file). The fix PRs touch `frontend/src/types/generated/api.ts` (generated artifact) and `frontend/src/hooks/useDoctorSectionTemplates.ts` + its new test — each documented in its own PR. **Denied paths:** backend business logic, migrations, CI config, secrets, live PHI, real bookings, payments, other PR edits, merge/deploy.
- **Validation performed:** full diff read of all ten merged PRs (~3,400 added lines); current-main source read of the six most-touched files (`useDoctorSectionTemplates.ts`, `DoctorServiceSelector.tsx`, `TeethChart.tsx`, `AIAssistant.tsx`, `useEMRAutosave.ts`, `CardiologistPanelUnified.tsx`); exact-head workflow-run records for all ten heads (actions runs + failed-job step inspection, incl. log retrieval for the freshness failure); per-ID GitHub search verifying ledger closures #3886 (120/120) and #3892 (27/27) and all RETRO fixes; local fail-first RED/GREEN run of the RETRO-3995-01 suite (vitest 5.0.3, node 24) plus the hook's existing suites and `tsc --noEmit`/eslint on the touched files. **NOT performed:** full frontend/backend test matrices, E2E, PostgreSQL concurrency probes, browser tests, staging, production, direct PR merges.
- **Rollback:** close this documentation Draft PR or revert its single Markdown addition; the two fix PRs are independently revertable.

**Verdict:** ten merged PRs catalogued, **all with zero formal GitHub Review at audit time** and four with PR Review Quality Gate failures at their exact heads; **two source-backed residual findings (P1 × 1 — main CI red, P2 × 1 — cross-context clinical phrases), both with fail-first reproductions and open fix PRs**. No P0 confirmed. This is a review dossier, not a blanket production-readiness sign-off.
