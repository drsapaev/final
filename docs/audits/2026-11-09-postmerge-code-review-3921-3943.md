# Consolidated post-merge Code Review — PR #3921–#3943

**Audit date:** 2026-11-09 (Asia/Tashkent). **Repository:** `drsapaev/final`.
**Purpose:** one durable, independent **documentation-only** retrospective for merged PRs; not a repair, not code sign-off for every path, and not a merge/deploy authorization.

## Executive summary

- PR numbers #3921–#3943 contain **17 merged PRs** and **2 open PRs** ([#3939](https://github.com/drsapaev/final/pull/3939), [#3943](https://github.com/drsapaev/final/pull/3943)); #3931–#3933 and #3936 return no pull request (404). Last available at census: #3943. These four missing numbers may still refer to issues or other objects; do not count them as unmerged PRs.
- Of **17 merged PRs**, **15** have **zero formal GitHub pull-request Review submissions** at the time queried. [#3937](https://github.com/drsapaev/final/pull/3937) has recorded reviews and two earlier P2 threads **resolved after source fixes**; [#3940](https://github.com/drsapaev/final/pull/3940) has two recorded reviews with no new confirmed P0–P2. **No review submission** is a gap in review evidence, not proof a fix is wrong.
- We read the PR patches/file inventories of **all 17** merged PRs, the review/thread histories of every available PR, and available GitHub CI status for the merged PR head commits. We examined relevant source and tests more deeply for payments, EMR, lab printing, medical file ownership, cardiology/Echo/ECG and dermatology. **We did not run unit tests, browser E2E, PostgreSQL concurrency, staging or production.** Source findings below are precise conditional failure paths, **not runtime-reproduced incidents**.
- **Six source-backed residual findings requiring fail-first tests:** **P1 × 3**, **P2 × 3**. No P0 observed in this bounded audit. All six are currently in merged runtime code; no follow-up remediation PR has been verified in this audit. Do not infer which patches have reached production.
- CI was generally green on inspected heads. [#3922](https://github.com/drsapaev/final/pull/3922) had an **earlier PR Review Quality Gate failure** among completed runs; [#3941](https://github.com/drsapaev/final/pull/3941) has two **cancelled** PR lifecycle/quality workflow runs alongside successes. Recorded green suites are not independent post-merge Code Review, do not prove every workflow path ran, and do not establish clinical release readiness.

## Source-backed residual findings (new; regression tests NOT executed)

### RETRO-3941-01 — P1 — ECG measurements can be submitted under another patient's ID after a selection switch

**Origin:** [#3941](https://github.com/drsapaev/final/pull/3941).
**Evidence:** [`frontend/src/pages/CardiologistPanelUnified.tsx 1972-1984`](https://github.com/drsapaev/final/blob/602eda5284f1b980b279130f4e11c1325373e8dc/frontend/src/pages/CardiologistPanelUnified.tsx#L1972-L1984) and [`frontend/src/components/cardiology/ManualEcgForm.tsx`](https://github.com/drsapaev/final/blob/602eda5284f1b980b279130f4e11c1325373e8dc/frontend/src/components/cardiology/ManualEcgForm.tsx).

The parent mounts `<ManualEcgForm patientId={selectedPatient...} visitId={...}>` when `showForm.open && showForm.type === 'ecg'`, **without an identity key**, and the `selectedPatient` change effect clears cached patient data but **does not close/reset `showForm`**. The new ManualEcgForm has local `useState(form)` initialized only at mount and no patient/visit identity reset. Therefore: type ECG measurements for patient A → switch selected patient to B while form remains open → local ECG fields still contain A's content but props now contain B's `patientId/visitId` → clicking Save POSTs those values under patient B. The form is rendered outside the conditional ECG tab and need not unmount upon tab navigation. This is a **potential clinical cross-patient record misattribution**.

**Fix/proof:** key form by canonical patient+visit and explicitly clear/close the open ECG form on owner change, ensure no unsaved A payload is permitted under B even during in-flight actions; add component and parent regression with A→B selection and source assertions, plus server-ownership negative test. Keep synthetic data only.

### RETRO-3941-02 — P1 — transient Echo hydration failure allows a partial edit to erase other saved Echo values

**Origin:** [#3941](https://github.com/drsapaev/final/pull/3941).
**Evidence:** [`frontend/src/components/cardiology/EchoForm.tsx 253-278`](https://github.com/drsapaev/final/blob/602eda5284f1b980b279130f4e11c1325373e8dc/frontend/src/components/cardiology/EchoForm.tsx#L253-L278), [`frontend/src/components/cardiology/EchoForm.tsx 325-339`](https://github.com/drsapaev/final/blob/602eda5284f1b980b279130f4e11c1325373e8dc/frontend/src/components/cardiology/EchoForm.tsx#L325-L339), [`frontend/src/components/cardiology/EchoForm.tsx 191-203`](https://github.com/drsapaev/final/blob/602eda5284f1b980b279130f4e11c1325373e8dc/frontend/src/components/cardiology/EchoForm.tsx#L191-L203).

On any initial GET failure other than expected 404 (e.g. a temporary 500/network failure), `useEffect.catch` replaces the form with `DEFAULT_ECHO_DATA` and resets `dirtyRef=false`, **without disabling Save or surfacing a retrieval failure**. The doctor can edit only EF. On Save the *second* `loadExistingEmrDraft` can succeed and return existing EDD/valve measurements/conclusion, but `buildEchoEmrPayload` assigns `specialty_data.echo = echoData` wholesale. Thus the blank form's untouched values overwrite previously stored fields while the changed EF saves successfully at the newest `row_version`. The successful-hydration and no-EMR-404 tests do not cover this failure order.

**Fix/proof:** fail closed for existing-EMR hydration errors (visible retry, no Save until canonical load); alternatively merge explicitly edited fields with the newly refetched persisted echo subtree and preserve unedited fields. Regression: GET#1 500 → edit EF → GET#2 returns full existing EF/EDD/conclusion → assert no destructive POST and preservation of other findings.

### RETRO-3941-03 — P1 — editing Echo while Save is in flight can make unsaved values appear saved

**Origin:** [#3941](https://github.com/drsapaev/final/pull/3941).
**Evidence:** [`frontend/src/components/cardiology/EchoForm.tsx 301-349`](https://github.com/drsapaev/final/blob/602eda5284f1b980b279130f4e11c1325373e8dc/frontend/src/components/cardiology/EchoForm.tsx#L301-L349) and [`frontend/src/components/cardiology/EchoForm.tsx 399-408`](https://github.com/drsapaev/final/blob/602eda5284f1b980b279130f4e11c1325373e8dc/frontend/src/components/cardiology/EchoForm.tsx#L399-L408) / [`frontend/src/components/cardiology/EchoForm.tsx 543-551`](https://github.com/drsapaev/final/blob/602eda5284f1b980b279130f4e11c1325373e8dc/frontend/src/components/cardiology/EchoForm.tsx#L543-L551).

`handleSave` disables only the **Save button** with `loading`; the input and conclusion handlers remain active during async GET/POST. The closure captures `echoData` at the time Save is invoked. If the doctor edits measurement B while that operation is in flight, the request persists captured A but the UI still shows B. On 200, `dirtyRef.current=false` is set without checking whether local edits happened after the submission started, so the form falsely shows saved status and a later pristine click may be skipped. This is a potential clinical data-loss/false-success path.

**Fix/proof:** disable all editor inputs during save or track edit epochs/snapshot version and preserve dirty state for edits made after request start; require a follow-up save when necessary. Regression with delayed GET and POST and an edit between start and ACK; verify the latest displayed value is not treated as persisted.

### RETRO-3930-01 — P2 — a late 403 from visit A can block valid edits on visit B

**Origin:** [#3930](https://github.com/drsapaev/final/pull/3930).
**Evidence:** [`frontend/src/hooks/useEMR.ts 175-181`](https://github.com/drsapaev/final/blob/e8c37dd36f3eb0d2bbd608c8bd5f26c8c05cbe29/frontend/src/hooks/useEMR.ts#L175-L181), [`frontend/src/hooks/useEMR.ts 256-267`](https://github.com/drsapaev/final/blob/e8c37dd36f3eb0d2bbd608c8bd5f26c8c05cbe29/frontend/src/hooks/useEMR.ts#L256-L267).

The `loadEMR` success path checks `stillCurrentVisit()` before dispatching B's data, but the **catch path** has `if (isAccessDeniedStatus(...)) return handleAccessDenied('loadEMR', apiError)` *without* the epoch check. `handleAccessDenied` unconditionally sets `writeAccessDeniedRef.current=true`, state `writeAccessDenied=true` and dispatches error. Thus A GET pending → switch to authorized B and load B → A GET rejects with 403 → B UI gets a spurious access-denied/save-disabled state even though the old visit is no longer current. Other late exceptions can write B's error state for the same reason. The new tests cover late successful GET but not late 403.

**Fix/proof:** guard every catch/error/denial and cache write/clear with visit+principal request identity; deferred A-403 after B-200 test asserting no B lock, no stale toast/error and successful B save.

### RETRO-3942-01 — P2 — loading page 2 cancels pending page 1 photo previews

**Origin:** [#3942](https://github.com/drsapaev/final/pull/3942).
**Evidence:** [`frontend/src/components/dermatology/DermaVisitGallery.tsx 140-157`](https://github.com/drsapaev/final/blob/841d29cac97f698b239c57f62d7903bbc17c5ae5/frontend/src/components/dermatology/DermaVisitGallery.tsx#L140-L157), [`frontend/src/components/dermatology/DermaVisitGallery.tsx 159-190`](https://github.com/drsapaev/final/blob/841d29cac97f698b239c57f62d7903bbc17c5ae5/frontend/src/components/dermatology/DermaVisitGallery.tsx#L159-L190), [`frontend/src/components/dermatology/DermaVisitGallery.tsx 205-242`](https://github.com/drsapaev/final/blob/841d29cac97f698b239c57f62d7903bbc17c5ae5/frontend/src/components/dermatology/DermaVisitGallery.tsx#L205-L242).

`loadGallery` starts background `void attachPreviews(imageFiles, seq)`, where every preview checks `seq === loadSeqRef.current`. `handleLoadMore` increments the **same global `loadSeqRef`** for page 2. Clicking "Показать ещё" before page 1 previews complete invalidates those previews, so the older page image cards stay placeholders even when their requests later succeed; subsequent batches of page 1 exit. This contradicts the stated independent preview/parallel pagination behavior.

**Fix/proof:** separate *context/list reset epoch* from *pagination request ID*, and track preview validity by file ID/context rather than invalidating prior pages on append; add deferred page-1 preview plus page-2 loading regression.

### RETRO-3921-01 — P2 — lost print-job ACK is treated as a confirmed failure, allowing a duplicate PDF fallback

**Origin:** [#3921](https://github.com/drsapaev/final/pull/3921).
**Evidence:** [`frontend/src/services/print.ts 101-125`](https://github.com/drsapaev/final/blob/95371667b55d2d8e8161f0069c9e63086ddfe97f/frontend/src/services/print.ts#L101-L125) and [`frontend/src/components/laboratory/LabReportWorkbench.tsx 953-963`](https://github.com/drsapaev/final/blob/95371667b55d2d8e8161f0069c9e63086ddfe97f/frontend/src/components/laboratory/LabReportWorkbench.tsx#L953-L963) / [`frontend/src/components/laboratory/LabReportWorkbench.tsx 1023-1035`](https://github.com/drsapaev/final/blob/95371667b55d2d8e8161f0069c9e63086ddfe97f/frontend/src/components/laboratory/LabReportWorkbench.tsx#L1023-L1035).

The new direct-print path correctly marks a malformed 2xx response as `ambiguous:true` and does NOT fall back. But its `catch(error)` **always** returns `ambiguous:false`, including a timeout or lost network response *after* the server accepted/queued the job. `handlePrint` interprets `ambiguous:false` as definite failure and automatically opens the PDF fallback. The physical job may already have been accepted, so the operator sees a second print route with an unconfirmed/unchanged report audit state.

**Fix/proof:** distinguish definite negative ACK/validation refusal from unknown transport result (timeout, response lost, disconnect, abort); mark unknown as `ambiguous:true`, stop fallback and require operator queue-status confirmation, never auto-retry an unknown physical print. Mock a queued backend job followed by client timeout; assert no duplicate/fallback.

## Complete merged PR inventory and formal-review status

All PRs below are **merged**, and changed-file inventories/patches were inspected. "No formal review" means no submission from `list_pull_request_reviews` at the audit snapshot; it does **not** say no one read the code. The last column tracks findings or limits, not complete validation.

| PR | Scope | Changed files | GitHub Review status | Source audit / follow-up |
| --- | --- | ---: | --- | --- |
| [#3921](https://github.com/drsapaev/final/pull/3921) | Lab reporting / canonical print | 16 | No formal review | RETRO-3921-01 P2 |
| [#3922](https://github.com/drsapaev/final/pull/3922) | EMR / laboratory list & epoch | 2 | No formal review | No confirmed new issue; CI/body history qualified |
| [#3923](https://github.com/drsapaev/final/pull/3923) | EMR / signature, restore, locking | 7 | No formal review | High-risk; focused re-review only |
| [#3924](https://github.com/drsapaev/final/pull/3924) | File upload / doctor visit ownership | 2 | No formal review | Source guard checked; negative paths require testing |
| [#3925](https://github.com/drsapaev/final/pull/3925) | Admin / profile setup navigation | 5 | No formal review | No confirmed new issue |
| [#3926](https://github.com/drsapaev/final/pull/3926) | Cashier / payment idempotency intent | 8 | No formal review | Fixes #3920 RETRO-FIN-001 by fingerprint; not independent sign-off |
| [#3927](https://github.com/drsapaev/final/pull/3927) | Derma+dental / price overrides | 14 | No formal review | Membership & truthful before-price inspected |
| [#3928](https://github.com/drsapaev/final/pull/3928) | TS migration / CI, auth logs | 11 | No formal review | No confirmed new issue |
| [#3929](https://github.com/drsapaev/final/pull/3929) | EMR / dirty/sign, amend, refresh | 14 | No formal review | High-risk; focused re-review only |
| [#3930](https://github.com/drsapaev/final/pull/3930) | EMR / principal cache & visit epoch | 7 | No formal review | RETRO-3930-01 P2 |
| [#3934](https://github.com/drsapaev/final/pull/3934) | DR drill / archive discovery | 2 | No formal review | No confirmed new issue; DR not operationally certified |
| [#3935](https://github.com/drsapaev/final/pull/3935) | Mutation / test deselection | 1 | No formal review | Not mutation-kill proof |
| [#3937](https://github.com/drsapaev/final/pull/3937) | Queue / T18 specialist E2E | 5 | Reviewed; both P2 threads resolved | Earlier two P2 fixed before merge |
| [#3938](https://github.com/drsapaev/final/pull/3938) | EMR / history, prescriptions, exam | 14 | No formal review | High-risk; focused re-review only |
| [#3940](https://github.com/drsapaev/final/pull/3940) | CI / RBAC trigger & i18n test | 2 | Reviewed twice; no confirmed P0–P2 | Backend RBAC scope caveat |
| [#3941](https://github.com/drsapaev/final/pull/3941) | Cardiology / ECG and Echo | 20 | No formal review | RETRO-3941-01/02/03 P1 |
| [#3942](https://github.com/drsapaev/final/pull/3942) | Derma gallery / async photos | 8 | No formal review | RETRO-3942-01 P2 |

**CI evidence:** checked the GitHub Actions workflow-run histories for all 17 merged PR HEAD commits. The counts above are run records (not individual test assertions): #3922 includes one earlier failed PR-body gate; #3941 includes two cancelled PR lifecycle/quality runs. For several high-risk PRs backend integration/staging scope is not established by a green overall CI record alone. The current-source RQ-18 full synthetic staging scenario is distinct from the standard Frontend E2E CI matrix.

## Existing review findings and remediation-chain reconciliation

- **Prior audit** [#3920](https://github.com/drsapaev/final/pull/3920) identified a P1 candidate RETRO-FIN-001 around payment idempotency replay. [#3926](https://github.com/drsapaev/final/pull/3926) adds `request_fingerprint` (endpoint + patient/visit(s) + amount + method) and compares it on preflight replay and concurrency recovery; client rotates request UUID on appointment-id change. This audit checked the source and test diff and treats **the original simple mismatch path as addressed in source**, but has **not** run PG races / validated all historical NULL-fingerprint anchors / independently signed off the merged fix.
- [#3937](https://github.com/drsapaev/final/pull/3937) initially had **two P2**: browser asset hashes from an independent refetch instead of the browser's response, and unverified persisted Service→specialists link. The later head hashes Playwright `Response.body()` and rereads the Service plus link count; both inline discussion threads were **resolved** on GitHub after an independent second review. **Do not re-open as residual defects** absent new contrary evidence. T18/Tier-2 remained PARTIAL in its own checkpoints.
- [#3940](https://github.com/drsapaev/final/pull/3940) has two formal Code Reviews showing no verified P0/P1/P2 in its narrow two-workflow change. Its backend RBAC integrity job is **not** a frontend route-guard behavioral test; the Russian-string detector scan stays advisory, while its new discovery regression is blocking. The review is not full-route authorization certification.
- The present six findings are **new follow-ups in other merged PRs**, not counts of historical already-resolved P2 comments.

## Follow-up implementation order / acceptance

1. **P1 clinical integrity:** [#3941](https://github.com/drsapaev/final/pull/3941) — protect ECG patient identity (RETRO-3941-01), fail-closed Echo hydration (02), and Echo edit/save epoch correctness (03). Write isolated failing tests against **old pinned SHA** with synthetic patient/visit A/B, then narrow fixes. Verify saved payload/owner with canonical backend and no unrelated data changed.
2. **P2 EMR context protection:** [#3930](https://github.com/drsapaev/final/pull/3930) — deferred stale `403` and stale `500` rejection after a new authorized visit; verify no false write-denial on B.
3. **P2 gallery and physical print:** [#3942](https://github.com/drsapaev/final/pull/3942) page-1 previews during page-2 loading; [#3921](https://github.com/drsapaev/final/pull/3921) unknown physical print outcome with no second action.
4. **Further independent reviews without new source-verified defect:** #3922/#3923/#3929/#3938 clinical lifecycle and signature audit; #3924 file ownership; #3926/#3927 payment/pricing and DB constraints; #3934 DR exercises. No claim that this bounded code-read establishes a full clinical or DR release certification.
5. For every fix, require exact final SHA, fail-first regression evidence, relevant backend/PG tests and negative tests where needed, independent formal GitHub Review **on final modified HEAD**, resolution or documented rebuttal of findings, and ledger status by finding ID. `SOURCE-CONFIRMED`, `REPRO-PENDING`, `FIXED-VERIFIED` and `NOT-REVIEWED` are separate states.

## Execution scope and limits

- **Mode:** `direct_execute` for **documentation-only** retrospective from inspected remote read-only GitHub evidence. The repo `AGENTS.md`, relevant React and CI review skills and affected source/test files were consulted. Risky product or migration changes require mandatory project agent gate and belong in **separate** narrowly scoped PRs.
- **Allowed first-touch path:** only this new `docs/audits/2026-11-09-postmerge-code-review-3921-3943.md`. **Denied:** all runtime/test/CI/migrations, DB, secrets, production, patient/payment writes, staging, original PR modifications, merging and deployment.
- **Evidence limits:** reviewed PR diffs, formal review histories, source contracts and recorded Actions; did not execute local test suites, actual browser, PostgreSQL races or integration/staging, so source findings need fail-first verification before declaring incidents. Historical merge success is not proof of production deployment.
- **Rollback:** close this draft PR or revert its single Markdown addition; no runtime state is changed.

**Verdict:** one consolidated tracking artifact for 17 merged PRs, 15 without formal review evidence, and six unresolved source-backed conditional hazards. **Do not merge this documentation PR as proof that all product fixes are clinically safe.**
