# Consolidated independent post-merge Code Review — PR #3969–#3996

**Date:** 2026-11-11 (Asia/Tashkent). **Repo:** `drsapaev/final`. **Census cut-off:** main head `440ec010aa` (merge commit of #3996, 2026-11-10T22:27:45Z) — the latest merged PR at review time. **Purpose:** documentation-only retrospective in a new dedicated PR; **NOT** a repair PR, exhaustive clinical acceptance or merge/deployment authorization.

**Post-audit status (2026-11-12; verified on `main` at `4651c1ff92108d990b112071bf51ace7a3d4bbc6`):** Both follow-up fixes have since merged: [#3998](https://github.com/drsapaev/final/pull/3998) at `2026-11-11T03:48:17Z` (merge commit `0d59c1005b71aa8e0f74a22352411cbb14dd41e2`) and [#3999](https://github.com/drsapaev/final/pull/3999) at `2026-11-11T04:10:14Z` (merge commit `cfb5b417be933f498db93f2248a39f464bfe7a7f`). These merges supersede the open/pending wording below for RETRO-3996-01 and RETRO-3995-01 at the census cut-off. They do not close the additional group-2 findings that #3999 does not cover. The census and source/CI evidence below remain pinned to `440ec010aa` and describe that earlier state.

## Executive summary

- PR numbers **#3969–#3996** contain **10 merged PRs** (all authored by `drsapaev`): #3969, #3970, #3971, #3972, #3986, #3988, #3992, #3994, #3995, #3996. **No PR in this interval was closed-unmerged** (#3987 and #3989 — earlier iterations of the #3986/#3988 fixes — were closed in favour of their successors before this census window). Open drafts (#3973–#3993 wave, #3958, #3961, #3968) do **not** enter the merged-remediation count.
- **All 10 merged PRs have zero recorded formal GitHub pull-request Reviews** at the audit snapshot, and the **PR Review Quality Gate failed at the exact heads of #3970 (×2), #3972 and #3988** before those merges. This records the absence of formal review submissions; it does not itself prove the implementations defective.
- **At the census cut-off, `main` was RED**: the Unified pipeline's *Generated API types freshness* step failed on `440ec010aa` (push run [42914777992](https://github.com/drsapaev/final/actions/runs/42914777992)); it had already failed at #3996's head `110f46a459` (run [42913774625](https://github.com/drsapaev/final/actions/runs/42913774625)) before the merge. See **RETRO-3996-01 (P1)**; #3998 later merged the generated types fix (see post-audit status above).
- **Two source-backed residual findings at the census cut-off** (fail-first reproducible): **P1 × 1, P2 × 1**. No confirmed P0. The follow-up PRs opened from this review were [#3998](https://github.com/drsapaev/final/pull/3998) (RETRO-3996-01) and [#3999](https://github.com/drsapaev/final/pull/3999) (RETRO-3995-01), both with fail-first regression evidence; both have since merged (see post-audit status above).
- **Ledger reconciliation:** audit-ledger **#3886 (120 findings) is closed at 120/120** (round 24 #3963 → round 30 #3994, which explicitly closes the ledger); **#3892 (27 findings, dental/dermatology) is closed at 27/27** (#3903/#3908 + follow-ups #3966/#3986); every RETRO from post-merge reviews **#3958** (RETRO-3947-01 → #3959; RETRO-3953-01 → #3992; RETRO-3953-02/03/04 → #3995) and **#3968** (RETRO-3963-01 → #3969; RETRO-3960-01 → #3988; RETRO-3965-01 → #3972; RETRO-3966-01 → #3986) has a merged fix.
- The **draft** ledger **#3961** (queue-position / WebSocket / notifications, 50 findings) is outside this review's range and actively processed by the owner (round 29 = #3996 merged; open drafts #3973–#3993). This audit deliberately does not duplicate that work.

## Findings — source-backed, fail-first reproduced

### RETRO-3996-01 — P1 — main was red at the census cut-off: openapi.json changed without regenerating the frontend API types

**Origin:** [#3996](https://github.com/drsapaev/final/pull/3996). **Sources:** `backend/openapi.json` (stats endpoint description changed), `frontend/src/types/generated/api.ts` (NOT regenerated), CI job logs of runs [42913774625](https://github.com/drsapaev/final/actions/runs/42913774625) (PR head `110f46a459`) and [42914777992](https://github.com/drsapaev/final/actions/runs/42914777992) (main head `440ec010aa`).

PR #3996 (QPOSAUTH-BE-001/002) edited `backend/openapi.json` — appending `Доступно: Admin, Registrar, Doctor (и SuperAdmin).` to the queue-position stats endpoint description — but did not run `npm run generate:api-types`. The Unified pipeline's freshness guard (`generate:api-types:check` → `git diff --exit-code src/types/generated/`) therefore failed with `API types are out of date! Run: npm run generate:api-types` **at the census cut-off**, leaving the freshness invariant (Phase 0.5 of the JS-to-TS migration plan) broken until the generated types fix merged. The failure was visible at the PR head before merging (pull_request run 42913774625, job `Frontend lint`, failed step `🔒 Generated API types freshness`) and was merged anyway.

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
| [#3996](https://github.com/drsapaev/final/pull/3996) | QPOSAUTH-BE-001/002 (audit #3961 round 29): stats endpoint staff-only, unlinked entries fail closed | 3 (+277/−14) | 8/10 (**Unified pipeline failure — API types freshness**, at head AND on main push 42914777992) | **RETRO-3996-01 (P1)** — main was red at the census cut-off (see finding) |

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

## Follow-up order and acceptance gates (at the census cut-off)

1. **P1 main-red freshness** ([#3998](https://github.com/drsapaev/final/pull/3998)): at the cut-off, merge only after the Unified pipeline is green on the PR head (the freshness step must pass); the repo's own regeneration pipeline is the fix, with no hand edits. #3998 later merged; see post-audit status above.
2. **P2 cross-context phrases** ([#3999](https://github.com/drsapaev/final/pull/3999)): the fail-first suite was RED on pre-fix source; require the existing principalSwap/consistency suites to stay green and independent code review on the final SHA per the AGENTS.md gate for EMR-adjacent changes. #3999 later merged; additional group-2 findings remain distinct.
3. The **PR Review Quality Gate failures at the exact heads of #3970/#3972/#3988** (formal review submissions) remain a process debt consistent with #3968's observation; the owner's draft policy #3975 proposes a verified gate before merging AI-authored PRs — this audit does not take a position on it.
4. At the cut-off, the two new finding IDs were `SOURCE-CONFIRMED / FAIL-FIRST-REPRODUCED / FIX-PENDING-MERGE`. After #3998 and #3999 merged, update the audit ledger with their merge evidence; keep group-2 findings that #3999 does not cover separate.

## Scope, validation and rollback

- **Execution mode:** `direct_execute` for **one documentation-only retrospective file** plus two narrowly scoped fix branches opened from this review (#3998, #3999), each with its own cyclic evidence in the PR body. This dossier does not modify clinical business rules or deployment policy.
- **First-touch / allowed path:** `docs/audits/2026-11-11-postmerge-code-review-3969-3996.md` only (this file). The fix PRs touch `frontend/src/types/generated/api.ts` (generated artifact) and `frontend/src/hooks/useDoctorSectionTemplates.ts` + its new test — each documented in its own PR. **Denied paths:** backend business logic, migrations, CI config, secrets, live PHI, real bookings, payments, other PR edits, merge/deploy.
- **Validation performed:** full diff read of all ten merged PRs (~3,400 added lines); current-main source read of the six most-touched files (`useDoctorSectionTemplates.ts`, `DoctorServiceSelector.tsx`, `TeethChart.tsx`, `AIAssistant.tsx`, `useEMRAutosave.ts`, `CardiologistPanelUnified.tsx`); exact-head workflow-run records for all ten heads (actions runs + failed-job step inspection, incl. log retrieval for the freshness failure); per-ID GitHub search verifying ledger closures #3886 (120/120) and #3892 (27/27) and all RETRO fixes; local fail-first RED/GREEN run of the RETRO-3995-01 suite (vitest 5.0.3, node 24) plus the hook's existing suites and `tsc --noEmit`/eslint on the touched files. **NOT performed:** full frontend/backend test matrices, E2E, PostgreSQL concurrency probes, browser tests, staging, production, direct PR merges.
- **Rollback:** close this documentation Draft PR or revert its single Markdown addition; the two fix PRs are independently revertable.

**Verdict:** ten merged PRs catalogued, **all with zero formal GitHub Review at audit time** and four with PR Review Quality Gate failures at their exact heads; **two source-backed residual findings at the census cut-off (P1 × 1 — main CI red, P2 × 1 — cross-context clinical phrases), both with fail-first reproductions**. Their follow-up PRs #3998/#3999 later merged; see post-audit status. No P0 confirmed. This is a review dossier, not a blanket production-readiness sign-off.

---

## Review group 2 — continuation (2026-11-11, independent second pass; same Draft PR)

**Method.** A second, independent review wave on the same pinned tree (`main` @ `440ec010aa`):
four parallel skeptical review passes over the full merged diffs of the window, each instructed
to try to **refute** every candidate before reporting it; the lead reviewer spot-verified the
four highest-severity pins directly on the pinned tree (`queue_position.py` role gates, cardio
hydration visit stamp, `LabReportWorkbench.tsx` noopener handling, `emr_v2.py` sign-endpoint
flat-key extraction). Executed on the pinned tree during this pass: cardiology contract suites
24/24 and full cardiology suite 124/124; ECG suites 31/31; dental readOnly suites 9/9 (+11/11
stabilized flakes +16 neighboring dental tests); #3970 suites 18/18; #3971 suites 16/16; #3994
suites 15 tests; #3995 suites 12 tests; #3996 backend integration suite 7/7 via a real local
TestClient harness (role matrix probed empirically); i18next interpolation probed against the
real frontend i18n config. **Census delta:** this pass also read **#3992** in full (the tenth
merged PR, RETRO-3953-01 principal-swap fix) — no new finding there; group 1's "no new
confirmed finding" verdict stands.

**Numbering.** Group 2 IDs continue the ledger without colliding with group 1: group 1 keeps
RETRO-3996-01 (openapi freshness P1) and RETRO-3995-01 (phrase-repaint P2); this group's
findings are RETRO-3996-02, RETRO-3995-02/-03, and RETRO-3969/3970/3971/3972/3986/3994-NN.
**17 numbered findings: P2 × 9, P3 × 8.** All are source-backed conditionals with fail-first
proposals; none is live-reproduced against production.

### Main-red process fact — a second red job on the same push run as RETRO-3996-01

`🐍 Backend тесты` is ALSO red on the main push run [42914777992](https://github.com/drsapaev/final/actions/runs/42914777992)
(check-run id 130174422089, failed step `🧪 Запуск тестов`, completed 2026-11-10T22:40:23Z,
attempt 1). The group-1 ledger records only the Frontend-lint/freshness failure. Evidence this
is a **flake-class failure, not a tree regression**: the merge commit `440ec010aa` carries the
same tree as #3996's PR head `110f46a459` (single-commit PR on base `3f35ed7c45`), where
`🐍 Backend тесты` completed **success** — same tree, different outcome. A rerun of the failed
jobs was fired from this review (`rerun-failed-jobs`, accepted 201, attempt 2 started
2026-11-11T02:24:03Z); its outcome is recorded in the PR comment thread. Recommendation:
group 1's follow-up order ("merge #3998 only after the Unified pipeline is green again on the
PR head") should equally require **Backend green on main** — a persistently red Backend job on
main masks real failures; if attempt 2 is red again, name the failing test from the job logs
and record its identity in this ledger (same discipline as the round-27/29
`test_lab_reporting_service` flake pattern already documented on #3972).

### Findings — group 2

#### PR #3969 (fix(cardio): every authoritative selection invalidates pending navigation intents)

Verdict: delivered as claimed (4 tickets, 5 invalidations, 13 rechecks verified by direct
count; all `setSelectedPatient` call sites covered). The guards discriminate patient identity
only — the visit dimension of the same steal scenario is uncovered.

- **RETRO-3969-01 (P2) — URL hydration reverts a committed same-patient / different-visit
  selection back to the stale URL `visitId` on every re-fire.** `hydratePatientFromUrl`
  re-fires on every selection change (`selectedPatient` in its dep array,
  `frontend/src/pages/CardiologistPanelUnified.tsx:739`); the entry bail returns only when
  patient AND visit already match (`:676–683`), `liveSelectionIsOtherPatient()` (`:701–706`)
  compares only patient ids, and the epoch guard passes (the row-click ticket was the last
  write). The merge stamps `visit_id: visitIdFromUrl || prev?.visit_id` (`:730`) over the
  doctor's chosen visit, hijacks the tab (`setActiveTab('patients')`, `:734`), and the P-019
  effect reloads the EMR for the URL visit — documentation entered afterwards lands on the
  stale visit (`VisitTab.tsx:149–150` binds the editor to `selectedPatient.visit_id`).
  Counter-evidence: the sibling URL-appointment sync **does** bail on visit mismatch
  (`:777–779`) — the guard was known and omitted here; the dermatology panel already fixed
  this exact class (`DermatologistPanelUnified.tsx:964–978`, `selectionContradictsUrl` checks
  patient **and** visit). Fail-first: source-contract slice asserting a visit-conflict bail
  precedes `await fetch(` in the hydration; behavioral variant — commit a row-click selection
  for P1/V_row at `?patientId=P1&visitId=V1`, bump `authRefreshTick`, assert
  `selectedPatient.visit_id` stays V_row and the tab stays `visit`.
- **RETRO-3969-02 (P3) — the hydration catch block toasts a load failure without any stale
  recheck.** `:736–738` `catch { notify.error(...) }` runs unconditionally; the identical
  defect class was fixed in `loadEMR`'s catch (`:1603` before the toast) and missed in this
  sibling. Fail-first: contract slice asserting an epoch recheck precedes `notify.error(`
  inside the hydration catch.

#### PR #3970 (fix(cardio): honest cardiology AI tab, services catalog and attachment preview planes)

Verdict: delivered as claimed, with residual gaps in the same defect classes — the PR fixed
the cardiology instances while sibling surfaces carrying the identical defect survived.

- **RETRO-3970-01 (P2) — lab PDF preview/print planes report a false "blocked" failure on
  every successful open (the exact CARDHIST-FE-001 class the PR declared fixed).**
  `window.open(url, '_blank', 'noopener,noreferrer')` returns `null` **on success** per the
  HTML spec when `noopener` is set; `frontend/src/components/laboratory/LabReportWorkbench.tsx:880–888`
  then renders `print_pdf_blocked` as an error whenever the returned handle is falsy — every
  genuinely opened PDF preview is reported as blocked; worse, in `handlePrint`'s PDF fallback
  (`:1070–1091`) the `if (popup)` arm is dead code in real browsers, so the LABPRINT-FE-002
  confirm-print button (`:1543–1551`) can never appear via the fallback. Counter-evidence:
  the lab tests mock `window.open` to return truthy `{}` (`LabReportPreview.contract.test.tsx:200–204,256`;
  `LabReportWorkbench.test.tsx:393`), masking the real null-return semantics; the PR's own
  `patientFilePreview` helper models the correct reserved-window pattern but only cardiology
  uses it. Fail-first: mock `window.open` to return `null` (real semantics), assert success
  feedback (not `print_pdf_blocked`) after «Предпросмотр PDF», and that the print fallback
  arms `pdfConfirmPendingInstanceId`.
- **RETRO-3970-02 (P3) — services-catalog empty fallback is honest only in Russian.**
  `frontend/src/components/doctor/DoctorServiceSelector.tsx:561,566` (plus `:478,:501`)
  hardcode Russian copy («Услуги не найдены», «Добавьте услуги…», «Код: », «мин») for the
  empty-catalog state; the *error* state is localized in all 5 locales, the empty state is
  not. Fail-first: render the selector with an empty catalog in a non-Russian locale, assert
  the empty-state text contains no Cyrillic.

#### PR #3971 (fix(emr): honest autosave conflict bookkeeping, canonical treatment completeness)

Verdict: partially — the honesty holds only for the exact sentinel each fix targeted.

- **RETRO-3971-01 (P2) — sign-endpoint section-template learning still reads only flat legacy
  keys (EMRLEARN-FE-001's exact defect, one call-site over).**
  `backend/app/api/v1/endpoints/emr_v2.py:498` computes
  `icd10_code = payload.data.get('icd10_code') or payload.data.get('icd_10_code')` — for the
  canonical nested `diagnosis.icd10_code` shape this yields `None`, so section templates
  persist unkeyed (`section_templates_service.py:112`) and the retrieval strategy
  (`:171–191`) never matches them — silently skipped personalization; when a nested I10 and
  stale flat I20 coexist, learning happens under the **wrong** code. Additionally `:504`
  builds treatment text without a `plan.treatment` fallback and raises `AttributeError` on
  list-shaped `medications`, silently skipping **all** section learning for that sign
  (`:521–523`). Counter-evidence: the service-level path uses canonical extractors
  (`emr_v2_service.py:484–485`), proving the canonical shape is the SSOT. Fail-first: sign a
  nested-ICD payload and assert `DoctorSectionTemplate.icd10_code == 'I10'` (not `None`);
  sign with list-shaped `medications` and assert the anamnesis template is still learned.
- **RETRO-3971-02 (P2) — a stale-visit save failure is still stamped as the last successful
  autosave, and `lastAutosave` is not visit-scoped.** `useEMR.saveEMR` returns `null` for a
  late failure of a previous visit (`frontend/src/hooks/useEMR.ts:422–426`); the honesty
  guards recognize only `accessDenied`/`conflict` (`useEMRAutosave.ts:134,156`), so `null`
  falls straight into success bookkeeping (`:161–164`). Reachable in the dermatology panel,
  which mounts `<EMRContainerV2>` **without a `key`** (`DermatologistPanelUnified.tsx:1704–1709`):
  after a visit switch `EMRStatusIndicator.tsx:184–196` renders "✓ saved" for the new visit's
  fresh editor though nothing was saved for it. Counter-evidence: cardiology keys the
  container per visit (`VisitTab.tsx:149`); the PR's conflict test never mocks a `null`
  resolution. Fail-first: `saveEMR.mockResolvedValueOnce(null)` → `forceSave()` → assert
  `lastAutosave` stays null and `onAutosaveSuccess` not called.
- **RETRO-3971-03 (P2) — FINALIZED_STATE 409 is surfaced as a false "another user changed the
  document" version conflict with undefined versions.** The backend deliberately returns
  structured 409 `{"error":"FINALIZED_STATE", …}` (`emr_v2.py:453–464`) for amendment routing;
  the client's 409 branch ignores `detail.error` (`useEMR.ts:397–409`) and dispatches
  `conflictDetected` without versions — the doctor sees «Документ был изменён другим
  пользователем» (false — it was **signed**) with literal `vundefined/vundefined`
  (`EMRConflictDialog.tsx:88–105`), and the amend affordance is gated on the *local* `isSigned`
  flag (`:154`), false in this scenario — the designed routing never appears. Counter-evidence:
  repo-wide grep finds no `FINALIZED_STATE` handling in `frontend/src`. Fail-first: mock a 409
  with `detail.error === 'FINALIZED_STATE'` and assert amendment-routed surfacing (or at
  minimum no `vundefined` and no false cause text).
- **RETRO-3971-04 (P2) — pending autosave is silently dropped on SPA navigation/unmount; only
  the browser `beforeunload` is guarded.** The autosave effect cleanup merely clears timers
  (`useEMRAutosave.ts:271–274`) with no flush; keystrokes inside the pending debounce window
  (`DEBOUNCE.autosave = 3000`) are discarded on in-app navigation; no router-level guard
  exists (single consumer of `useNavigationGuard`). Exposure is unbounded while autosave is
  paused after 3 consecutive errors (`canSave` blocked at `:87`). Fail-first: render
  `isDirty=true`, advance timers into a pending debounce, unmount, assert a flush attempt (or
  a new `onAutosaveDropped` callback) occurred.

#### PR #3972 (fix(cardio): P-wave axis is never relabeled as the QRS electrical axis)

Verdict: delivered as claimed (`axis` = qrsAxis only, explicit null, `pAxis` separate;
verified incl. viewer persistence and metric-card gating; no other reader repo-wide). Two P3
residuals inside the same claim perimeter.

- **RETRO-3972-01 (P3) — `exportECGParameters` still interchanges the two axes (the inverse
  relabel of what the PR fixed).** `frontend/src/components/cardiology/ECGParser.tsx:359`
  `p: parameters.pAxis || parameters.axis` exports the QRS axis as the P-wave axis whenever
  `pAxis` is absent or exactly `0`; `:360` reads a key the parser never emits. Latent (zero
  call sites today). Fail-first: `exportECGParameters({axis:90, pAxis:null})` → assert
  `axis.p === null`; `({axis:90, pAxis:0})` → assert `axis.p === 0`.
- **RETRO-3972-02 (P3) — a measured 0° QRS axis hides the heart-axis card and leaks a bare
  "0" text node.** `frontend/src/components/cardiology/ECGViewer.tsx:965`
  `{ecgParameters.axis && (…)}`: a legal measured `0°` is falsy — React renders the raw `0`
  as a stray text node instead of the «Электрическая ось сердца: 0°» card. Pre-dates the PR
  (TS migration `f2c868a19`); a remaining defect in the PR's blast radius. Fail-first: drop an
  XML with `<qrsAxis value="0"/>`, assert the card renders with `0°` and no bare `0` node.

#### PR #3986 (fix(dental): locked records open an inspection-only ToothModal)

Verdict: delivered as claimed (full verification: readOnly prop, fail-closed guard before the
only write, honest banner, disabled controls, Save not rendered, contract passed down from
`DentalVisitScreen`, TeethChart inspection-only routing, emr-v2 consumer wired, i18n key × 5;
suites 9/9 + 11/11 + 16 neighbors green). No P1/P2 gap survived.

- **RETRO-3986-01 (P3, latent — unreachable on current main) — third ToothModal consumer
  (DentistDialogsLayer) bypasses the inspection-only contract entirely.**
  `frontend/src/pages/dentist/views/DentistDialogsLayer.tsx:262–280` renders `<ToothModal>`
  with **no `readOnly` prop** and its TeethChart hardcoded `readOnly={false}` (`:214`); the
  path has no record-lock concept. Currently dead UI (entry not destructured by
  `DentistPanelUnified.tsx:249–273`, render entry removed `:414–418`, no hotkey binding) — a
  live writable-modal bypass the day the handler is re-wired. Fail-first: source-contract case
  in `RETRO3966.readOnlyWiring.contract.test.tsx` asserting the DentistDialogsLayer invocation
  carries `readOnly` (or the entry is deleted).
- **RETRO-3986-02 (P3) — inspection banner is untranslated outside Russian.**
  `dental2.tooth_inspection_only` carries identical Russian copy in en/kk/uz-Cyrl/uz-Latn
  (`en.ts:6627`, `kk.ts:6627`, `uz-Cyrl.ts:6638`, `uz-Latn.ts:6627`) — extends the pre-existing
  Russian `dental2` block pattern (parity complete; no raw-key fallback). Fail-first: locale
  parity check asserting the `en.ts` value differs from `ru.ts` for this key.

#### PR #3988 — zero findings (group 2 confirms group 1's verdict, with refutations on record)

Group 2's independent pass also found no surviving defect: the channel-equality chain
(`_visits.py:143–144`), the fresh-path persistence/dispatch, and the replay truthfulness were
re-derived, with the type-coercion, changed-channel-plus-other-field, and foreign-row
candidates refuted at source level. Both passes agree: **#3988 is the cleanest merge of the
window.**

#### PR #3994 (fix(emr): native text undo stays with the browser; amended records show signed provenance)

Verdict: partially — native-undo claim delivered (no interception left); the timestamp
provenance is broken at runtime, and the reducer redo hotkey is dead on real Latin keyboards.

- **RETRO-3994-01 (P3) — signed/amended provenance tooltip renders a raw i18n placeholder,
  not the timestamp.** `frontend/src/components/emr-v2/EMRStatusIndicator.tsx:165–167` passes
  `{ lastSaved: formatAbsoluteTime(lastSaved) }`, but the locale value is
  `'Подписана {formatAbsoluteTime(lastSaved)}'` — a JS-expression-style placeholder — in all
  five locales (`ru.ts:9520`, `en.ts:9390`, `uz-Latn.ts:9386`, `uz-Cyrl.ts:9397`,
  `kk.ts:9386`); the app's single-brace i18next interpolation (`i18n/index.ts:90–96`) cannot
  substitute it (verified empirically against the real config). Counter-evidence: the sibling
  key `esi_sohraneno_v_absolutetime` (`ru.ts:9525`) interpolates correctly — the config works,
  the spelling is the defect; the PR's own test mocks `t`, so real interpolation was never
  exercised. Fail-first: substitute with i18next-style single-brace over the real `ru.ts`
  strings, assert the title contains the formatted time and no `{`.
- **RETRO-3994-02 (P3, remaining) — document-wide redo (Ctrl+Shift+Z) is unreachable on real
  Latin-layout browsers.** `frontend/src/hooks/useEMRKeyboard.ts:116` matches
  `(e.key === 'z' || e.key === 'я') && e.shiftKey`, but real browsers report `'Z'`/`'Я'`
  (uppercase) when Shift is held — the branch never matches outside jsdom; only Ctrl+Y works
  (`:123`). The PR's test dispatches lowercase `{key:'z'…}`, asserting semantics real browsers
  don't produce. Fail-first: dispatch `{key:'Z', ctrlKey:true, shiftKey:true}` (and `{key:'Я'}`)
  with `canRedo` and assert `onRedo`.

#### PR #3995 (fix(emr): template context transitions, forced refresh and shared-GET failures are honest)

Verdict: partially — group 1 already recorded RETRO-3995-01 (mutation repaint, fix #3999).
Group 2 adds two findings in the same honesty perimeter that the #3999 fix does **not** cover.

- **RETRO-3995-02 (P2) — forced refresh is per-instance: a late pre-mutation GET from another
  mounted instance overwrites the post-mutation cache and view.** The epoch cache-write guard
  (`epoch === requestEpochRef.current`, `frontend/src/hooks/useDoctorSectionTemplates.ts:262–271`)
  compares against the *writing* instance's per-`useRef` counter while the cache is
  module-global (`:39`); a forced refresh (`:296–300`) cannot bump other instances' epochs.
  Co-mounted same-key instances are a supported configuration:
  `AnamnesisMorbiSection.tsx:71–75` and `AnamnesisVitaeSection.tsx:48–52` both pass
  `section:'anamnesis'` with `icd10Code:null` when the EMR has no ICD yet — identical
  cacheKey. With instance A on a slow GET and instance C doing PUT + fresh GET over the same
  key, A's late resolution still passes its own epoch check and writes OLD over NEW into the
  shared cache (`:267–270`), commits OLD locally and to joiner B (`:181–187`); later readers
  then get OLD with no network call (`:217–224`) — the "successful PUT, old text rendered"
  symptom RETRO-3953-03 claimed to fix, surviving via the multi-instance route. **Why #3999's
  fix does not close it:** the `liveCacheKeyRef` defense checks the request's cacheKey against
  the live cacheKey — in this scenario both are the **same** key; only the write's TIME is
  stale. Counter-evidence: no cross-instance invalidation exists; the PR's RETRO-3953-03
  test is single-instance. Fail-first: mount A with a deferred GET; run C's `updateTemplate`
  with a fast fresh GET; resolve the stale GET last; assert A (and a fourth mount D) read
  `'NEW'` and D makes no extra GET.
- **RETRO-3995-03 (P2) — no consumer renders the hook's `error`, so a failed shared GET still
  presents as an honest "no templates" success.** The fix sets `error` on joiner and
  originator (`:184–187`, `:282–285`), but all seven consumers destructure only
  `templates/loading/hasTemplates` (`ComplaintsSection.tsx:56–61`, `NotesSection.tsx:40–50`,
  `AnamnesisMorbiSection.tsx:65–75`, `AnamnesisVitaeSection.tsx:42–52`,
  `RecommendationsSection.tsx:38–48`, `ExaminationSection.tsx:80–90`,
  `DoctorTemplatesPanel.tsx:61–67`); the panel renders its empty state
  (`DoctorTemplatesPanel.tsx:194–206`) — the exact "honest-looking no-templates success" the
  PR's dossier describes as the defect. Fail-first: mock `api.get` to reject, render the
  panel, assert it does NOT show the empty state and DOES show an error/retry affordance.

#### PR #3996 (fix(queue): position stats are staff-only and unlinked entries fail closed)

Verdict: partially — both headline mechanisms are real and server-side (route-level
`require_roles`, honest typed 403 on unlinked entries, 7-test suite green), but the
"staff-only" allow-list **excludes the canonical doctor family** — a regression introduced by
this window, distinct from group 1's openapi-freshness P1.

- **RETRO-3996-02 (P2, introduced regression) — position endpoints lock out the doctor-family
  roles (cardio/derma/dentist).** `require_roles("Admin","Registrar","Doctor")`
  (`backend/app/api/v1/endpoints/queue_position.py:196,227`) admits only the exact "Doctor"
  spelling; `_normalize_required_roles` (`app/core/security.py:84–105`) lowercases but never
  expands the family, while `Roles.CARDIO/DERMA/DENTIST` are canonical level-7 doctor roles
  (`app/core/roles.py:31–33`) and the repo's own SSOT says doctor-family gates must spread
  `DOCTOR_FAMILY_GATE_ROLES` (`roles.py:175–185`, the D-3 unification note). The same
  vocabulary mismatch sits in the inline staff tuples (`:135`, `:176` —
  `current_user.role not in ("Admin","Registrar","Doctor","SuperAdmin")`), so a `cardio`
  doctor is also 403'd on every entry read. Empirically confirmed on current source via a
  local TestClient harness: role `cardio` → stats 403, entry-by-id 403, by-number 403 (even
  for the cardio doctor's own queue); role `Doctor` → 200/200. Pre-fix, `get_current_user`
  admitted cardio — this PR regressed that access. Counter-evidence: the module's own
  `_ensure_doctor_can_notify_entry` enumerates cardio/derma/dentist as expected module
  callers (`:31–39`); the PR's tests cover Patient/Registrar/Doctor only. Fail-first: add a
  `cardio`-role doctor (own queue with a waiting entry) to
  `backend/tests/integration/test_queue_position_authorization.py` and assert the stats GET
  and the own-entry read return 200.

### Cross-PR patterns (group 2)

1. **Point-fixes leave the class alive in siblings** — #3970 minted the canonical honest
   preview transport yet the identical `noopener` false-block survives twice in
   `LabReportWorkbench.tsx`; #3971 minted the canonical extraction chain yet the identical
   flat-key read survives in `emr_v2.py:498`. A structural guard (source-contract test or
   ESLint `no-restricted-syntax`) would catch both.
2. **Falsy-zero on clinical numbers** — `toFiniteNumber` returns `0` as a valid measurement;
   every `||`/`&&` truthiness branch on its output is a latent 0°-value bug
   (RETRO-3972-01/-02). A shared `isMeasured(v) => v !== null` helper closes the class.
3. **Role-vocabulary divergence (D-3 recurrence)** — `queue_position.py` now carries three
   divergent vocabularies (`require_roles`, the inline capitalized tuple, and
   `QUEUE_POSITION_DOCTOR_NOTIFY_ROLES`) while `roles.py` exports `DOCTOR_FAMILY_GATE_ROLES`
   precisely to prevent this drift (RETRO-3996-02).
4. **Expression-style i18n placeholders that can never interpolate** —
   `{formatAbsoluteTime(lastSaved)}`, `{Math.round(autosaveConfig.debounceMs / 1000)}` at
   `ru.ts:9520,9523,9526` and the same lines ±5 in all five locales (systemic, pre-existing;
   RETRO-3994-01 is one instance).
5. **Test-boundary masking** — `window.open` mocked truthy; `t` mocked (real interpolation
   never exercised); single-instance tests miss cross-instance cache races; the
   doctor-family role matrix is absent from the RBAC tests though the repo SSOT calls it
   out. The three strongest group-2 P2s all hide exactly at these boundaries.
6. **URL deep-link clobber** — derm fixed the class with `selectionContradictsUrl` covering
   patient **and** visit; the cardio epoch covers patient identity only (RETRO-3969-01) —
   a precedent port, not a new invention.

### Follow-up order (group 2, extends group 1's)

1. **RETRO-3996-02** — production authorization regression introduced by this window
   (empirical TestClient proof on record); fix = spread the doctor family
   (`DOCTOR_FAMILY_GATE_ROLES`) in both the stats gate and the inline tuples; fail-first
   cardio-role test.
2. **RETRO-3969-01** — patient/visit-context steal; port the derm `selectionContradictsUrl`
   visit dimension into `hydratePatientFromUrl`; close RETRO-3969-02 in the same PR
   (sibling catch).
3. **EMR write/learn integrity cluster — RETRO-3971-01** (canonical extraction in the sign
   endpoint; list-`medications` robustness), then **3971-02/-03/-04** (autosave honesty:
   null-result guard, visit-scoped reset, FINALIZED_STATE routing, unmount flush).
4. **Template/shared-cache — RETRO-3995-02/-03** (cross-instance epoch invalidation +
   consumers rendering `error`) — note #3999 fixes group 1's RETRO-3995-01 only; and
   **RETRO-3970-01** (reserved-window pattern port to LabReportWorkbench + test unmasking).
5. P3s opportunistically with their owning P2 fix or as a small i18n/falsy-zero hygiene PR
   (RETRO-3970-02, 3986-02, 3994-01 share the i18n hygiene surface; RETRO-3972-01/-02 share
   the falsy-zero helper).
