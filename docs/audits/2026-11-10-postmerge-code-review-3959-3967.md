# Consolidated independent post-merge Code Review — PR #3959–#3967

**Date:** 2026-11-10 (Asia/Tashkent). **Repo:** `drsapaev/final`. **Census cut-off:** #3967, latest PR visible immediately before creating this audit. **Purpose:** documentation-only retrospective in a new dedicated PR; **NOT** a repair PR, exhaustive clinical acceptance or merge/deployment authorization.

## Executive summary

- PR numbers **#3959–#3967** contain **9 real PRs**: **5 merged** ([#3959](https://github.com/drsapaev/final/pull/3959), [#3960](https://github.com/drsapaev/final/pull/3960), [#3963](https://github.com/drsapaev/final/pull/3963), [#3965](https://github.com/drsapaev/final/pull/3965), [#3966](https://github.com/drsapaev/final/pull/3966)); **4 open** ([#3961](https://github.com/drsapaev/final/pull/3961), [#3962](https://github.com/drsapaev/final/pull/3962), [#3964](https://github.com/drsapaev/final/pull/3964), [#3967](https://github.com/drsapaev/final/pull/3967)); **0 closed-unmerged** in this exact interval. Open PRs do **not** enter the merged-remediation count.
- **All 5 merged PRs have zero recorded formal GitHub pull-request Reviews at the audit snapshot**. This means the remote GitHub Review API has no submissions; it does not prove no human inspected the code and does not itself prove the implementation defective.
- Inspected all five merged PR diffs/file lists, GitHub Review and inline-thread metadata for all nine PRs, recorded workflow-run results for the exact head commits of all five merged PRs, and targeted source/tests in the canonical cardiodiagnostic, doctor scheduling, patient-navigation and dentistry flows. No fresh local Vitest, pytest, E2E, PostgreSQL race, staging or production run was performed.
- **Four source-backed residual conditional findings** to reproduce before patching: **P1 × 1**, **P2 × 3**. No confirmed P0 in the bounded source audit. All are shown on pinned merged-head source with synthetic fail-first test proposals. They are **not observed patient incidents**.
- Historical follow-up: [#3959](https://github.com/drsapaev/final/pull/3959) implements a touched-field draft overlay around Echo hydration Retry from [#3958](https://github.com/drsapaev/final/pull/3958) finding RETRO-3947-01, including dedicated regression tests; exact-head CI is green. The earlier loss path should **not** be re-counted as unresolved absent contrary reproduction.

## Findings — source-backed conditional paths (not runtime-reproduced)

### RETRO-3963-01 — P1 — a late appointment navigation can steal a newer queue/patient selection

**Origin:** [#3963](https://github.com/drsapaev/final/pull/3963). **Sources:** [`frontend/src/pages/CardiologistPanelUnified.tsx:1031-1067`](https://github.com/drsapaev/final/blob/f2e9edb08837c7e47924403bd7c6b73b17154a26/frontend/src/pages/CardiologistPanelUnified.tsx#L1031-L1067), [`frontend/src/pages/CardiologistPanelUnified.tsx:1893-1949`](https://github.com/drsapaev/final/blob/f2e9edb08837c7e47924403bd7c6b73b17154a26/frontend/src/pages/CardiologistPanelUnified.tsx#L1893-L1949), [`frontend/src/pages/CardiologistPanelUnified.tsx:1127-1164`](https://github.com/drsapaev/final/blob/f2e9edb08837c7e47924403bd7c6b73b17154a26/frontend/src/pages/CardiologistPanelUnified.tsx#L1127-L1164).

The new `navigationEpochRef` increments only in three appointment-derived paths: appointment row click, `view_emr` and `complete`. The other authoritative patient switches (`handlePatientSearchPick`, `handleDoctorQueueStartVisit`, `handleDoctorQueueOpenVisit`) call `setSelectedPatient` but **do not invalidate the navigation epoch**. Reproducible interleaving in source: click appointment A → `ensureCanonicalVisitId(A)` awaits → switch to patient/queue B → B becomes selected → old A lookup resolves, sees its old epoch still current, and `setSelectedPatient(A)` / `loadEMR(A)` / `goToTab('visit')` steals the active clinical context. The same failure can occur with `view_emr`/complete. The added `CardiologistPanel.patientIdentity.contract.test.tsx` exercises epoch guards for appointment paths but does not cover cross-entry A→B selection while A's lookup is pending.

**Impact:** wrong active patient's clinical screen can appear after the doctor chose another patient; this is a clinical-context integrity risk, not proof that the backend wrote another patient's record.

**Fail-first test/fix:** deferred `ensureCanonicalVisitId(A)` then select B through each queue and search callback; resolve A and assert B remains selected, B's EMR and active-tab intent survive; also defer `loadEMR(A)` *after* initial selection and switch to B. Centralize *all* patient/visit selections under one navigation-intent invalidation (including unmount and explicit close), plus post-await checks after every async boundary.

### RETRO-3960-01 — P2 — schedule-next deduplication ignores changed confirmation channel but reports the NEW channel without sending it

**Origin:** [#3960](https://github.com/drsapaev/final/pull/3960). **Sources:** [`backend/app/api/v1/endpoints/doctor_integration/_visits.py:96-141`](https://github.com/drsapaev/final/blob/a88cf9afbc503b610777838a46c27384c91a4857/backend/app/api/v1/endpoints/doctor_integration/_visits.py#L96-L141), [`backend/app/api/v1/endpoints/doctor_integration/_visits.py:364-412`](https://github.com/drsapaev/final/blob/a88cf9afbc503b610777838a46c27384c91a4857/backend/app/api/v1/endpoints/doctor_integration/_visits.py#L364-L412), [`backend/app/api/v1/endpoints/doctor_integration/_visits.py:428-440`](https://github.com/drsapaev/final/blob/a88cf9afbc503b610777838a46c27384c91a4857/backend/app/api/v1/endpoints/doctor_integration/_visits.py#L428-L440).

`_find_recent_identical_schedule_next` matches patient, doctor, date/time, discount, notes and service lines, but **does not match `Visit.confirmation_channel`**. The persisted visit records the original request's channel. A second request within the 10-second replay window with otherwise identical services but a **different channel** is silently deduplicated. Its replay response sets `confirmation.channel=request.confirmation_channel` and `notification_sent=false`, while **no notification is sent to that new channel and the persisted visit retains the original channel**. The caller gets a success response announcing the requested channel without performing that channel's workflow. Separate from the deliberate policy of not resending a true identical retry.

**Fail-first test/fix:** first schedule using `phone`, then an immediate same-terms `telegram` request; assert that a successful response's `confirmation.channel` always matches the persisted visit and that any requested channel change is either explicitly applied and notified according to product policy or rejected with a truthful conflict. Safer default: include channel in intent equality and make changed-channel handling explicit; never claim new channel delivery without proof.

### RETRO-3965-01 — P2 — fallback substitutes P-wave axis for QRS electrical axis and classifies it clinically

**Origin:** [#3965](https://github.com/drsapaev/final/pull/3965). **Sources:** [`frontend/src/components/cardiology/ECGParser.tsx:97-110`](https://github.com/drsapaev/final/blob/3698e283f1f26915aefa71c751849ccb42a5f472/frontend/src/components/cardiology/ECGParser.tsx#L97-L110), [`frontend/src/components/cardiology/ECGParser.tsx:301-315`](https://github.com/drsapaev/final/blob/3698e283f1f26915aefa71c751849ccb42a5f472/frontend/src/components/cardiology/ECGParser.tsx#L301-L315), [`frontend/src/components/cardiology/ECGViewer.tsx:458-506`](https://github.com/drsapaev/final/blob/3698e283f1f26915aefa71c751849ccb42a5f472/frontend/src/components/cardiology/ECGViewer.tsx#L458-L506).

The parser correctly prioritizes `qrsAxis` when present, but when it is absent it uses `pAxis` as the generic `parameters.axis`. Downstream `analyzeECGParameters` treats **that value as QRS electrical axis**, using the QRS-specific left/right thresholds; ECGViewer persists the generic axis into structured `/cardio/ecg`. P-axis orientation is **not a substitute for QRS axis**: a document with `<pAxis value="-55"/>` but **no** `qrsAxis` will spuriously produce QRS-left-axis classification and save `axis="-55"` instead of unknown. This is a retained legacy fallback within the changed parser contract, not an allegation that this PR invented the fallback. Existing added test checks QRS precedence when *both* tags exist, but not a P-only document.

**Fail-first test/fix:** parse XML with `pAxis=-55`, absent QRS axis and otherwise valid rhythm/measurement; assert `axis=null`, `axis_not_measured` and null structured axis while keeping P-axis data separate if needed. Source data should never be clinically relabelled; distinguish `pAxis` and `qrsAxis` in the DTO.

### RETRO-3966-01 — P2 — locked/read-only tooth chart opens an editable modal that can attempt EMR write

**Origin:** [#3966](https://github.com/drsapaev/final/pull/3966). **Sources:** [`frontend/src/components/dental/DentalVisitScreen.tsx:1594-1600`](https://github.com/drsapaev/final/blob/fd24f40055c03155541c236d99e7ff9c71f808ac/frontend/src/components/dental/DentalVisitScreen.tsx#L1594-L1600), [`frontend/src/components/dental/DentalVisitScreen.tsx:1700-1713`](https://github.com/drsapaev/final/blob/fd24f40055c03155541c236d99e7ff9c71f808ac/frontend/src/components/dental/DentalVisitScreen.tsx#L1700-L1713), [`frontend/src/components/dental/DentalVisitScreen.tsx:1743-1753`](https://github.com/drsapaev/final/blob/fd24f40055c03155541c236d99e7ff9c71f808ac/frontend/src/components/dental/DentalVisitScreen.tsx#L1743-L1753), [`frontend/src/components/dental/ToothModal.tsx:363-401`](https://github.com/drsapaev/final/blob/fd24f40055c03155541c236d99e7ff9c71f808ac/frontend/src/components/dental/ToothModal.tsx#L363-L401), [`frontend/src/components/dental/ToothModal.tsx:604-613`](https://github.com/drsapaev/final/blob/fd24f40055c03155541c236d99e7ff9c71f808ac/frontend/src/components/dental/ToothModal.tsx#L604-L613).

The chart's new `readOnly` branch rightly avoids `onToothClick`, but the parent connects **`onInspect={handleToothClick}`**, which opens the full `ToothModal` even when `fieldsDisabled=true` because of a signed EMR, incomplete hydration or completion. `ToothModal` has **no `readOnly/disabled` prop**, exposes editable fields and enabled Save when content is meaningful, and its Save directly attempts `POST /v2/emr/{visitId}`. A signed document should be rejected by the backend; this report **does not claim a successful unauthorized write**. The defect is a misleading editable interface and attempted mutation despite the declared read-only clinical UI contract. In the `DentistrySection` consumer, the inverse gap also exists: `readOnly` TeethChart receives `onToothClick` but **no `onInspect`**, so buttons may be enabled yet do nothing on inspection.

**Fail-first test/fix:** mount DentalVisitScreen with a signed/locked EMR and click a tooth; assert inspection-only UI with **no editable controls or Save** and **no `POST /v2/emr`** regardless of user interaction. Pass an explicit inspection/read-only mode to the modal or render a dedicated tooth inspection view; cover both dental consumers and keyboard activation.

## Full merged inventory and formal-review evidence

| PR | Scope | Changed files | Exact-head CI run records | GitHub formal review | Audit verdict |
| --- | --- | ---: | --- | --- | --- |
| [#3959](https://github.com/drsapaev/final/pull/3959) | Echo Retry draft preservation + locale/test | 7 | **8 successful, 0 failed** | None | Source fix + regression suite present for old RETRO-3947-01; no new confirmed finding in this bounded read |
| [#3960](https://github.com/drsapaev/final/pull/3960) | Doctor schedule-next: dedup, all_free, time/date, doctor identity | 5 | **8 successful, 0 failed** | None | RETRO-3960-01 P2; downstream confirmation contract needs channel-aware test |
| [#3963](https://github.com/drsapaev/final/pull/3963) | Cardiology patient hydration/navigation/edit race | 3 | **8 successful, 0 failed** | None | RETRO-3963-01 P1; cross-entry navigation race |
| [#3965](https://github.com/drsapaev/final/pull/3965) | ECG parser strict validation & device DTO | 8 | **9 successful, 1 failed PR Review Quality Gate run** | None | RETRO-3965-01 P2; P/QRS axis provenance |
| [#3966](https://github.com/drsapaev/final/pull/3966) | Dentistry controlled data, tooth chart read-only & clear all | 6 | **9 successful, 1 failed PR Review Quality Gate run** | None | RETRO-3966-01 P2; inspection/edit authorization UX boundary |

**CI caveat:** `fetch_commit_workflow_runs` returns available PR-triggered run *records* at the pinned head, not exhaustive test assertions. The historical failed PR Review Quality Gate runs for #3965/#3966 must not be masked by other successful jobs. No evidence here that the full synthetic clinical E2E/staging paths were executed by this reviewer; review count and test count are different metrics.

## Open PRs (excluded from post-merge conclusions)

| PR | State and context |
| --- | --- |
| [#3961](https://github.com/drsapaev/final/pull/3961) | Open docs-only queue/WebSocket audit; separate review needed |
| [#3962](https://github.com/drsapaev/final/pull/3962) | Open Palette accessibility/UI changes; separate review needed |
| [#3964](https://github.com/drsapaev/final/pull/3964) | Open booking staging acceptance evidence; this is not an already completed acceptance |
| [#3967](https://github.com/drsapaev/final/pull/3967) | Open clinical EMR AI suggestion plane; needs standalone pre-merge review and relevant guardrails |

## Reconciliation with previous consolidated reviews

- [#3958](https://github.com/drsapaev/final/pull/3958) documented **RETRO-3947-01**: initial failed Echo hydration → clinician types → Retry discards unsaved draft. **Merged [#3959](https://github.com/drsapaev/final/pull/3959)** adds `draftTouchedRef`/current-form ref and overlays touched fields onto the canonical reload, preserving the typed draft and untouched server fields; dedicated `EchoForm.retryDraft.test.tsx` covers this flow. Reviewed source patch and exact-head CI; **no new runtime repro by this audit**. Mark historical issue as `FIX_PRESENT_SOURCE / INDEPENDENT_RUNTIME_REPRO_NOT_RUN`, not as an unresolved new P2.
- Earlier [#3958](https://github.com/drsapaev/final/pull/3958) also had four #3953 template-cache findings; **#3953 is outside this audit's requested range**, and no fix for those is asserted by these five unrelated merges.
- #3960 / #3963 / #3965 / #3966 contain substantial protective changes and tests, but a passing suite does not cover newly identified negative interleavings. This report preserves their positive evidence while identifying missing cases.

## Follow-up order and acceptance gates

1. **P1 clinical wrong-context navigation** ([#3963](https://github.com/drsapaev/final/pull/3963)): fail-first synthetic A→B transitions involving appointment promise and direct queue/search switch; guard every entry path and any outstanding post-selection await; independent code review on final fix SHA.
2. **P2 read-only safety and ECG provenance** ([#3966](https://github.com/drsapaev/final/pull/3966), [#3965](https://github.com/drsapaev/final/pull/3965)): tooth inspection cannot offer a save or attempt write in locked EMR; P-axis cannot populate QRS-axis diagnostic field; test backend rejection and parser/structured-output consistency.
3. **P2 scheduling confirmation truthfulness** ([#3960](https://github.com/drsapaev/final/pull/3960)): change-channel during dedup window must not return a success claiming a channel the server did not store or notify.
4. Carry forward history into this same audit ledger with finding IDs, status `SOURCE-CONFIRMED / REPRO-PENDING / FIX-VERIFIED / ACCEPTED-RISK`. Do not merge a fix solely because a developer replied "fixed"; require targeted fail-first regression, relevant full tests and fresh exact-head formal review.
5. Current `AGENTS.md` mandates project gate for *implementation* touching clinical EMR, canonical contract, scheduling and queue ownership. These code changes belong in separate narrowly scoped branches/PRs with synthetic data; this docs-only report does not authorize clinical behavior change.

## Scope, validation and rollback

- **Execution mode:** `direct_execute` for **one documentation-only retrospective file**. This does not modify clinical business rules or deployment policy. Read `AGENTS.md` and the relevant React review skill. Mandatory `ai/langgraph/scripts/run_agent_gate.ps1` for later clinical/contract implementation was **not run** for this pure documentation ledger. Canonical sources are read-only references.
- **First-touch / allowed path:** `docs/audits/2026-11-10-postmerge-code-review-3959-3967.md` only. **Denied paths:** all backend/frontend executable files, tests, migrations, CI, infra/config, secrets, live PHI, real bookings, payments, other PR edits, merge/deploy.
- **Validation performed:** PR census and statuses #3959–#3967; review/thread histories all nine; patches/file inventories all five merged; exact-head workflow runs all five; targeted full source/test excerpts for new code and adjacent consumers; static scenario reasoning. **NOT performed:** fresh local or remote test executions, PostgreSQL/booking concurrency probes, browser tests, staging, production, patient records, direct PR merge.
- **Rollback:** close this documentation Draft PR or revert its single Markdown addition. No app/database behavior changes.

**Verdict:** five merged PRs catalogued, **five with no formal GitHub Review at audit time**, **four source-backed conditional regression targets (P1 × 1, P2 × 3)**. No P0 confirmed. This is a review dossier, not a blanket production-readiness sign-off.
