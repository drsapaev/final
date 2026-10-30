# Registrar frontend — cumulative code-review ledger

> **Status:** IN PROGRESS / documentation-only; not a release or approval report.
> **Started:** 2026-10-29 (Asia/Tashkent). **Repository:** `drsapaev/final`.
> **Baseline:** `main` at `9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1`.
> **Review type:** source inspection via GitHub file reads. **No runtime or automated tests were executed for these findings.**
> **Purpose:** retain every actionable review finding with source evidence, reproduce/verify it, and agree on a safe remediation sequence **after** the review inventory is complete.

## Execution boundary

- Mode: `direct_execute` for **one narrow, documentation-only review-ledger change**. No queue/clinical/payment behavior is modified.
- Authorized write scope: **this Markdown document only** on the dedicated audit branch; review evidence is read-only.
- Excluded: application source and tests, backend, migrations, configuration, production, deployments, live data, merges, and changes to queue ownership/fairness.
- Stop point: do not implement fixes in this audit PR. Reassess ownership and run the repository-mandated gate(s) before any later implementation PR involving queue/clinical/payment contracts.
- Validation for this documentation change: fetch the committed file and inspect the PR diff. CI and runtime tests remain unexecuted until explicitly checked; do not infer a green build.

## Status and severity legend

- `SOURCE-OBSERVED`: the described code path exists in the frozen baseline.
- `REPRO-PENDING`: an end-to-end or focused regression test still must demonstrate the user-visible effect.
- `CONFIRMED`: focused failing test or equivalent verified reproduction; **none yet**.
- `RESOLVED`: regression is fixed with tests and reviewed in a **separate fix PR**; no entries resolved yet.
- Severity P0–P3 is **provisional** until verification and triage; no P0/P1 demonstrated during this first pass.

## Findings index

| ID | Severity (provisional) | Area | Source observation | Status | Proposed fix/test batch |
| --- | --- | --- | --- | --- | --- |
| REG-FE-001 | P2 | Worklist row activation | Click/keyboard row activation invokes a logger-only callback rather than record preview | SOURCE-OBSERVED / REPRO-PENDING | Batch A: table interaction |
| REG-FE-002 | P2 | All-departments search | Search results omit the service-normalization step present in unfiltered results | SOURCE-OBSERVED / REPRO-PENDING | Batch B: pure worklist presentation |
| REG-FE-003 | P3 | Localization | `filteredAppointments` memo uses a translated fallback but does not depend on it | SOURCE-OBSERVED / REPRO-PENDING | Batch B: pure worklist presentation |
| REG-FE-004 | P2 | Welcome quick filters | Queue-status filters `queued`/`paid_pending` exclude backend `waiting` or payment-pending records | SOURCE-OBSERVED / REPRO-PENDING | Batch C: filter semantics |
| REG-FE-005 | P2 | URL date and worklist | Changing `?date` while mounted does not directly reload when calendar is closed; worklist heading still says today | SOURCE-OBSERVED / REPRO-PENDING | Batch D: date lifecycle |
| REG-FE-006 | P2 | Welcome actions | `in_cabinet`/`complete` commands lack confirmations present in the main table | SOURCE-OBSERVED / REPRO-PENDING | Batch A: action consistency |
| REG-FE-007 | P2 | Rate-limit handling | HTTP 429 returns without failure/stale state; tests explicitly pin a `loading=false`/`dataSource=loading` quirk | SOURCE-OBSERVED / REPRO-PENDING | Batch D: fetch state |
| REG-FE-008 | P2 | Refresh feedback | Welcome manual refresh announces success synchronously, before fetch outcome | SOURCE-OBSERVED / REPRO-PENDING | Batch D: fetch feedback |
| REG-FE-009 | P2 | Reschedule presentation | Optimistic deletion compares IDs from different record namespaces, potentially hiding an unrelated row | SOURCE-OBSERVED / REPRO-PENDING | Batch E: reschedule UI |
| REG-FE-010 | P2 | Existing patient selected in create mode | Form changes to existing patient profile are not sent to patient update API on create path | SOURCE-OBSERVED / REPRO-PENDING | Batch F: patient identity/profile UX |
| REG-FE-011 | P2 | Partial patient save before edit | `updatePatient` can commit changes before later queue/edit-delta failure | SOURCE-OBSERVED / REPRO-PENDING | Batch G: patient/visit atomicity |
| REG-FE-012 | P2 | Date-aware service catalogue | Older async service response can overwrite newer catalogue and rehydrate current cart | SOURCE-OBSERVED / REPRO-PENDING | Batch H: wizard data loading |
| REG-FE-013 | P2 | Wizard diagnostic privacy | Direct patient-phone string and `fio` object field can pass through development logger | SOURCE-OBSERVED / REPRO-PENDING | Batch I: privacy guard |

### REG-FE-001 — Row activation does not open details (P2 candidate)

**Code evidence:**

- [WorklistView.tsx L289–L301](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/views/WorklistView.tsx#L289-L301) passes an `onRowClick` callback that calls only `logger.info(...)`; comment indicates a details dialog could be opened, but no detail action is invoked.
- [EnhancedAppointmentsTable.tsx L211–L223](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/components/tables/EnhancedAppointmentsTable.tsx#L211-L223) forwards a supplied `onRowClick` to `DataTable`, making the callback part of the row-activation contract.
- [useRegistrarRowActions.ts](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/useRegistrarRowActions.ts) already supplies `openRecordPreview` and a working `view` action for explicit action controls.

**Potential impact:** a registrar clicks/keyboard-activates a row expecting to inspect the record, but nothing visible happens. Do not conflate this with the separate explicit `view` action, which may still work.

**Reproduction / fail-first test:** render `WorklistView` with one synthetic record; trigger the table row with a pointer and Enter/Space; assert an intentional details action occurs (or, if UX contract specifies non-actionable rows, assert row activation/focus affordance is absent). Check actual `DataTable` semantics and accessibility before selecting the remedy.

**Preferred remediation:** after verifying the intended UX, either wire row activation to `openRecordPreview` through an explicit prop/callback, or remove the misleading row-activation wiring. Preserve separate `view` and `edit` workflows, and verify keyboard activation and click-on-action-button behavior.

### REG-FE-002 — Search bypasses all-departments service normalization (P2 candidate)

**Code evidence:**

- [registrarWorklistRows.ts L275–L294](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/registrarWorklistRows.ts#L275-L294) returns `sortRegistrarRowsForPresentation(searched)` directly when `searchQuery` is present. The no-query path applies `filterServicesByDepartment(..., null, services)` to each row.
- [registrarServiceFilter.ts](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/registrarServiceFilter.ts) explicitly has a fallback from `queue_numbers[].service_name` when the aggregate `services` array is empty.

**Potential impact:** for an aggregated patient with no `services` array but queue numbers that can provide service codes, all-departments view may show services *before* entering a search term and omit them *after* searching. Only a **display** problem is alleged; there is no evidence of a backend queue/appointment mutation.

**Reproduction / fail-first test:** in `registrarWorklistRows.test.ts`, use synthetic data with a stable patient key, `queue_numbers` containing a service-name/code resolvable by `toServiceCode`, and `services: []`. Compare `computeRegistrarWorklistRows` with `searchQuery: ''` versus a query matching the patient; assert that the displayed services are equal. First establish that this data shape is supported by the current adapter/API.

**Preferred remediation:** apply the *same* presentation-only postprocessing to searched and unsearched aggregated rows, without changing queue identity, grouping, timing, ordering or server-owned routing. Regression test both search branches and multi-record aggregates.

### REG-FE-003 — Localized fallback not tracked by memo (P3 candidate)

**Code evidence:**

- [RegistrarPanel.tsx L259–L268](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/RegistrarPanel.tsx#L259-L268) passes `tI18n('registrarPanel.rp_unknown_patient')` into `computeRegistrarWorklistRows`, while the `useMemo` dependency array omits that resolved translated string and the translator/language.

**Potential impact:** when UI language changes without a concurrent change to the listed dependencies, a record lacking the patient display name may retain a fallback label in the previous language. Scope is limited to display text, not patient identity or data persistence.

**Reproduction / fail-first test:** render a registrar worklist with one **synthetic** record whose patient name is unavailable; change locale while keeping appointment/service/profile references stable; assert the fallback text updates. Do not add a test that passes solely because data reload changes an unrelated dependency.

**Preferred remediation:** compute `fallbackPatientLabel` as a render value and include that value in the memo dependency array; keep translated fallbacks separate from canonical patient data.


### REG-FE-004 — Quick filters disagree with backend queue/payment status semantics (P2 candidate)

**Code evidence:**

- [WelcomeView.tsx L392–L408](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/views/WelcomeView.tsx#L392-L408) writes `?status=queued` for "Активная очередь" and `?status=paid_pending` for "Ожидают оплаты".
- [registrarWorklistRows.ts L188–L192 and L239–L243](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/registrarWorklistRows.ts#L188-L243) compare that URL status strictly against `entry.status` on both detail and aggregate pathways; `payment_status` is not used for the payment filter.
- [Backend registrar _helpers.py L46–L50](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/backend/app/api/v1/endpoints/registrar_integration/_helpers.py#L46-L50) preserves the server queue status `waiting` (and defaults absent/paid status to `waiting`); [registrarQueueAdapter.ts L46–L48 and L87–L94](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/registrarQueueAdapter.ts#L46-L94) stores canonical queue status separately from `payment_status`.

**Potential impact:** an active `waiting` patient may be absent from the "active queue" view, and a patient whose **payment_status** is pending may be absent from "awaiting payment" if their queue status is `waiting`. Status aliases/permissions may change exact affected sets; validate against real canonical DTOs before deciding which statuses represent "active".

**Fail-first test:** with synthetic backend records `{status:'waiting',payment_status:'pending'}`, exercise both Welcome filters and `computeRegistrarWorklistRows`; assert active-queue and unpaid filters follow the chosen backend-owned semantics. Cover both department and aggregate tabs, and confirm no status mutation is introduced.

**Fix direction:** separate UI filter concepts `queueStatus` and `paymentStatus` or interpret legacy URLs through a single canonical backend-aligned predicate. Keep backend queue and payment truth distinct, preserve existing shared URLs or migrate them intentionally.

### REG-FE-005 — Worklist date may diverge from `?date` (P2 candidate)

**Code evidence:**

- [useRegistrarWorklistData.ts L243–L250](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L243-L250) chooses the API date from `searchParams.get('date')` when calendar mode is not active.
- [useRegistrarWorklistData.ts L401–L477](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L401-L477) loads once at mount and reloads on calendar state/date changes, but no dedicated `?date` dependency effect when `showCalendar === false`. Changing search params rebuilds `loadAppointments` but the guarded initial effect does not load again.
- [WorklistView.tsx L145–L154](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/views/WorklistView.tsx#L145-L154) always labels the worklist "today" when calendar is closed, even if the initial API request used a historical `?date`. [QueueView.tsx L82–L99](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/views/QueueView.tsx#L82-L99) can change the URL date.

**Potential impact:** direct navigation to `/registrar?date=YYYY-MM-DD` can show historical rows under a "today" label. Editing `?date` through same-mounted navigation can retain data from the earlier date until another refresh. This is a **presentation/data-loading mismatch**, not proof that the server stores records under the wrong date.

**Fail-first test:** mount the hook with a non-today URL date, assert request `target_date` and visible date heading; rerender with another URL date while `showCalendar=false`, assert a new request and correct rows. Test back/forward and concurrent responses.

**Fix direction:** derive one effective worklist date and make the data-loading effect depend on it, not every incidental filter or appointment-count change; reuse the request sequence guard; render that effective date consistently in the header.

### REG-FE-006 — Welcome table bypasses action confirmation (P2 candidate)

**Code evidence:**

- [WelcomeView.tsx L641–L659](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/views/WelcomeView.tsx#L641-L659) routes `in_cabinet` and `complete` directly to `updateAppointmentStatus` without a confirmation.
- [useRegistrarRowActions.ts L89–L129](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/useRegistrarRowActions.ts#L89-L129) awaits a shared confirmation before the same actions on the main table, and [useRegistrarRowActions.test.ts](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/__tests__/useRegistrarRowActions.test.ts#L1-L15) documents that contract.

**Potential impact:** where the backend exposes these actions to the current role, a misclick in the Welcome table can send a state-changing command without the confirmation protection used elsewhere.

**Fail-first test:** render the Welcome table with synthetic record/action permissions and trigger `in_cabinet`/`complete`; verify no network command occurs unless the user confirms. Also verify keyboard activation and explicit action buttons do not double-submit.

**Fix direction:** route Welcome commands through the *same* `useRegistrarRowActions` handler or one centralized confirmation-aware action service. Preserve backend RBAC and available-actions checks.

### REG-FE-007 — HTTP 429 fails to produce an explicit refresh-failure state (P2 candidate)

**Code evidence:**

- [useRegistrarWorklistData.ts L347–L357](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L347-L357) sets 60-second cooldown and returns on 429 without `LOAD_FAILED` or a rate-limit-specific state.
- [useRegistrarWorklistData.test.ts L204–L212](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/__tests__/useRegistrarWorklistData.test.ts#L204-L212) explicitly pins the existing `dataSource='loading'`, `appointmentsLoading=false` outcome for a non-silent 429. This is **known preserved behavior**, not an unanticipated code typo.

**Potential impact:** on primary load, the worklist may leave the spinner but not show the intended error/retry state; on refresh, kept data may not be visibly marked stale despite the failed attempt. A user could mistake the state for a healthy/empty result.

**Fail-first test:** mock a 429 on initial load and after a successful load, assert explicit rate-limited/retry feedback and preserved rows; confirm auto-refresh respects the cooldown. Update the legacy test only when intentionally replacing the pinned behavior.

**Fix direction:** model rate limiting as an explicit state, preserving previous rows with stale indication, exposing the cooldown/retry action, and avoiding a false success claim. No backend throttling change in this audit.

### REG-FE-008 — Manual refresh announces success before the outcome (P2 candidate)

**Code evidence:** [WelcomeView.tsx L418–L423](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/views/WelcomeView.tsx#L418-L423) calls `loadAppointments(...)` without awaiting it and immediately calls `notify.success(t('misc.data_updated'))`. The data hook catches network errors internally, so a `Promise<void>` resolution alone is not currently proof of successful refresh.

**Potential impact:** the registrar can see "data updated" despite a failed API request/429, while the table still displays old or no data.

**Fail-first test:** stub a pending/rejected/429 fetch, click Refresh, assert no success toast before a verified successful response; assert an appropriate failure or rate-limit indication. Test a successful refresh separately.

**Fix direction:** expose a reliable fetch-result outcome from the hook (rather than assuming any awaited void return means success), then show success only for a current, successful request. Preserve last-known data on failure.

### REG-FE-009 — Reschedule optimistic removal mixes ID namespaces (P2 candidate)

**Code evidence:**

- [useRegistrarReschedule.ts L33–L80](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/useRegistrarReschedule.ts#L33-L80) unions raw `id`, `visit_id`, `queue_entry_id`, `appointment_id` and aggregate IDs as **untyped strings**, then removes any row with *any* matching ID.
- [RescheduleSlots.tsx L99–L107](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/views/RescheduleSlots.tsx#L99-L107) invokes the optimistic removal after the reschedule succeeds, before queue reload.

**Potential impact:** IDs from different tables may overlap. Example (synthetic): rescheduling row A `{id:10,visit_id:20}` puts `20` in the removal set; unrelated row B `{id:20,visit_id:21}` is hidden because `B.id=20`, even though B is a different entity. The normal refresh may restore B; a failed refresh could prolong a misleading worklist state. Backend reschedule identity is unaffected by this specific client-side filter.

**Fail-first test:** use two synthetic records with overlapping cross-table IDs and different canonical record refs; call `removeRescheduledAppointmentFromView` for A; assert only the intended row disappears. Add multiple-record aggregate and failed-refresh cases.

**Fix direction:** compare type-scoped canonical record references, not bare cross-entity IDs. If a safe identity is not available, do not remove optimistically; let an authoritative reload determine the list.


### REG-FE-010 — Existing patient profile edits may not persist in create mode (P2 candidate)

**Code evidence:** [AppointmentWizardV2.tsx L850–L872](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L850-L872) stores the selected patient's `id` and editable form data; [PatientStepV2.tsx L290–L323](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/PatientStepV2.tsx#L290-L323) exposes birth date and address editing. On submit, [AppointmentWizardV2.tsx L2069–L2115](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2069-L2115) calls `createPatient` only when `!editMode && !patientId`. With `editMode === false` and the explicitly selected patient's non-null ID, that branch is skipped. The subsequent cart creation carries `patient_id` and service/quote fields but no patient profile changes ([L2690–L2702](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2690-L2702)).

**Potential impact:** registrar chooses an existing patient, corrects address or birth date in the creation form, and successfully creates an appointment; the displayed correction is not saved to the patient card. This is contingent on those fields being intended as editable patient-profile data in create mode (product contract to verify).

**Fail-first test:** select an existing synthetic patient and change their address/birth date, submit a new appointment. Assert the resulting patient record reflects the intended changes or that the UI explicitly prevents/makes clear that profile edits will not be saved. Confirm the cart is linked to the existing patient ID and never silently creates a second patient.

**Remediation direction:** choose and document the workflow contract: update the existing profile through an explicit, independently verified patient-card save, or make profile fields read-only in booking mode with a deliberate "Edit patient" action. Avoid implicit phone/FIO reassociation.

### REG-FE-011 — Separate patient mutation before queue edit can yield a partial save (P2 candidate)

**Code evidence:** [AppointmentWizardV2.tsx L2180–L2196](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2180-L2196) calls `await updatePatient(patientId, { sex: ... })` before entering the queue/full-update/edit-delta paths. The later [edit-delta API call L2425–L2467](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2425-L2467) is an independent mutation that may reject (including quote/concurrent-update 409). A QR lookup path also updates an attached patient before the edit is committed ([L1992–L2025](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L1992-L2025)).

**Potential impact:** when editing a queued visit, the patient sex/birth date/address can persist, followed by a rejected edit-delta/queue operation. The wizard reports an unsuccessful appointment edit while the patient record has already changed. This is a **partial cross-domain operation**, not evidence of wrong patient identity or a failed backend transaction.

**Fail-first test:** with synthetic patient and queue entities, mock `updatePatient` success followed by `applyRegistrarEditDelta` rejection (409) or QR full-update failure. Assert the user receives truthful **partial-save** feedback, the patient card outcome is known, and retry cannot silently duplicate commands. Check the canonical backend ownership/transaction model before designing any atomicity change.

**Remediation direction:** avoid a pre-save outside the authoritative edit operation when possible. Prefer backend transaction-aware command ownership if the domain allows it; otherwise explicitly surface the successful patient write and failed queue command, and prescribe safe reconciliation. Any modification requires the repository mandatory gate due to patient/clinical/queue boundaries.

### REG-FE-012 — Stale service catalogue can overwrite active wizard data (P2 candidate)

**Code evidence:** [AppointmentWizardV2.tsx L914–L951](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L914-L951) fetches a date-specific service catalogue, then unconditionally calls `setServicesData` / `setFilteredServices` on resolution, with no generation guard or abort. [L1045–L1060](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L1045-L1060) invokes the loader when `isOpen` or the loader identity/date changes. [L1009–L1039](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L1009-L1039) uses the resulting `servicesData` to resolve currently displayed cart references.

**Potential impact:** open wizard for date A, start catalogue fetch; then open/edit record for date B while request A remains pending. If B resolves first and A later, A's catalogue can replace B's and hydrate the B cart against obsolete doctor/service metadata. Backend validation still owns queue assignment and may reject; this finding concerns misleading frontend choices/quote and potential wrong user decision, not proven unauthorized assignment.

**Fail-first test:** with deferred promises, return date B before date A, assert that current selected date B catalogue stays visible and cart references/eligibility are not overwritten by A. Also test closing/reopening the wizard and a request failure after a successful catalogue load.

**Remediation direction:** use an abort signal or monotonic request-ID/active-date guard; reset or explicitly mark catalogue stale during a date/record change. Verify quote and doctor-selection data update coherently.

### REG-FE-013 — Development logging leaks patient-identifying strings (P2 privacy candidate)

**Code evidence:** [AppointmentWizardV2.tsx L2034–L2046](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2034-L2046) constructs a `logger.warn(`...${wizardData.patient.phone}...`)` message with the raw phone in a **primitive string**. [L1931–L1940](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L1931-L1940) passes `{ fio, phone, birth_date }` as a log object. [logger.ts L15–L41](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/utils/logger.ts#L15-L41) does not list the bare field name `fio`, and [L146–L171](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/utils/logger.ts#L146-L171) passes primitive strings through without sanitization. Logger `warn` and `log` output only in development by default, so **no production log emission from these specific logger methods has been shown**.

**Potential impact:** real patients' phone or name can appear in developer console during edit-mode QR patient resolution in development/test builds. This violates the repository privacy discipline even if production builds normally suppress these logger methods.

**Fail-first test:** in a synthetic-only logger test, pass a fabricated phone in an interpolated string and `{ fio: 'SYNTHETIC Patient' }`; assert outputs are redacted (or replace these call sites with non-PII diagnostic facts) without weakening error observability. Verify production/dev behavior separately.

**Remediation direction:** remove patient values from diagnostic message strings; log only safe flags/record-kind/error-code. Harden logging conventions so primitive PHI cannot bypass scrubber. Keep this entirely separate from patient/queue behavior changes.

### Wizard follow-up investigation (not yet a numbered finding)

There remains an older [batch endpoint + fallback branch in AppointmentWizardV2.tsx L2495–L2590](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2495-L2590): after a batch error it can continue toward cart creation. The earlier `editDeltaBuild.items.length > 0` return and the QR full-update short-circuit appear to guard most real edit scenarios; **reachability and duplicate-write impact are not proven**. Do not label P1 or change the branch without a fail-first route-selection test and backend reconciliation evidence. The main `createRegistrarCart` path already uses a submission lock and payload-bound idempotency key.

## Review coverage

### Actually inspected in first pass (source reads; not an exhaustive audit)

- `frontend/src/pages/RegistrarPanel.tsx`
- `frontend/src/pages/registrar/registrarWorklistRows.ts`
- `frontend/src/pages/registrar/registrarServiceFilter.ts`
- `frontend/src/pages/registrar/useRegistrarWizard.ts`
- `frontend/src/pages/registrar/useRegistrarNavigation.ts`
- `frontend/src/pages/registrar/useRegistrarRowActions.ts`
- `frontend/src/pages/registrar/useRegistrarHotkeys.ts`
- `frontend/src/pages/registrar/views/WorklistView.tsx`
- `frontend/src/pages/registrar/views/RegistrarDialogsLayer.tsx`
- `frontend/src/components/tables/EnhancedAppointmentsTable.tsx`
- `frontend/src/utils/registrarAggregation.ts`
- `frontend/src/utils/logger.ts`
- `frontend/src/api/registrar.ts`
- `frontend/src/components/wizard/AppointmentWizardV2.tsx`
- `frontend/src/components/wizard/wizardUtils.ts`
- `frontend/src/components/wizard/PatientStepV2.tsx`
- `frontend/src/components/wizard/CartStepV2.tsx`
- `frontend/src/components/dialogs/ModernDialog.tsx`
- `frontend/src/api/queue.ts` and `frontend/src/api/mappers/queue.ts`
- Selected wizard regression/contract tests in `frontend/src/components/wizard/__tests__/`
- `frontend/src/pages/registrar/views/WelcomeView.tsx`
- `frontend/src/pages/registrar/views/QueueView.tsx`
- `frontend/src/pages/registrar/useRegistrarWorklistData.ts`
- `frontend/src/pages/registrar/useRegistrarReschedule.ts`
- `frontend/src/pages/registrar/useRegistrarCalendar.ts`
- `frontend/src/pages/registrar/views/RescheduleSlots.tsx`
- `backend/app/api/v1/endpoints/registrar_integration/_helpers.py` and relevant `_today_queues.py` mapping (read-only contract evidence)
- Focused source-contract / worklist test files were partially inspected to identify regression-test owners.

### Outstanding review slices (partially audited where noted)

1. Registration and editing: `AppointmentWizardV2`, wizard state, save/error paths and patient lookup (initial save-path review complete; full route/test coverage pending).
2. Queue read-model: `useRegistrarWorklistData`, `registrarQueueAdapter`, `QueueView`, queue profile navigation; read-only comparison with canonical backend DTOs and ADR-001.
3. Record actions: fuller audit of `useRegistrarActions`, backend command status/identity/error handling, cancellation, call/complete/reschedule (initial front-end read completed).
4. Display and usability: `WelcomeView`, table renderers, modal accessibility, loading/empty/error states.
5. API/privacy/performance: registrar API adapter, outbound requests, auth boundaries, PHI-safe diagnostics, existing tests/e2e.

Any further findings receive the next stable ID (`REG-FE-014`, etc.), a source-SHA anchor, an impact scenario, a reproduction/test, and a status. If refuted, mark **NOT A BUG** with evidence rather than silently deleting the row.

## Remediation plan — execute only after review triage

1. **Freeze and verify:** complete relevant review slices; fetch latest `main` and compare the old anchored evidence with the new baseline. Confirm each candidate using a fail-first focused unit/component/e2e test; close false positives without editing application code.
2. **Triage risk and ownership:** address confirmed P0/P1 before P2/P3. If any fix touches queue ownership/fairness, clinical lifecycle, payment truth, authentication or API contracts, run the repository-required execution gate and inspect canonical source, ADRs and backend tests before editing.
3. **Batch A — interaction:** `REG-FE-001`; decide desired row-click UX, add keyboard/pointer regression, smallest implementation change, review, CI.
4. **Batch B — view model/localization:** `REG-FE-002` + `REG-FE-003` only if they remain purely presentation-level and independently tested; avoid altering backend SSOT and identity.
5. **Additional batches:** one bounded fix PR per validated domain/root cause; never introduce a speculative blanket refactor or mix unrelated source fixes into this ledger PR.
6. **Validation:** relevant Vitest components/contracts, `tsc`/ESLint, affected Playwright flows with synthetic data, relevant queue contract tests, PR quality gates, `git diff --check`, and code review. Record **actual commands/results**; do not claim tests passed without execution.
7. **Closure:** update each ledger row with root cause, test evidence, fix PR/commit SHA, review outcome, and resolution status. Keep this audit PR as the index; merge it only when repository review and CI policy permit. Do not deploy as part of this audit.

## Change log

| Date | Ledger revision | Added / updated | Verification |
| --- | --- | --- | --- |
| 2026-10-29 | Initial | Three provisional source-observed findings; coverage, scope and remediation plan | GitHub source reads; remote PR/commit verified |
| 2026-10-29 | Review pass 2 | REG-FE-004–009: quick filters, URL date, Welcome confirmation, 429 handling, refresh notification, reschedule identity | Frontend hooks/views, backend read-model helpers and existing tests inspected; runtime tests not executed |
| 2026-10-30 | Review pass 3 | REG-FE-010–013: existing patient edits, partial profile/queue save, stale wizard catalogue, development PII logging | Wizard UI/handlers, API mappers, privacy logger, wizard tests inspected; no runtime tests executed; new main source SHA `22b21a8b7c3c0b9b56f4e388c35e329a4321f768` |

## End-of-review acceptance criteria

- Every finding has a unique stable ID and a final disposition: `CONFIRMED`, `NOT A BUG`, `DUPLICATE`, or `RESOLVED`.
- Confirmed defects have focused regression tests; no test exists merely to silence a failure.
- Changes preserve backend queue fairness, identities, clinical/payment ownership, RBAC, and privacy guardrails.
- Fix PRs are reviewed, all required CI is green, and the final ledger links to those PRs/commits.
- This document by itself is **not evidence** that the registrar workflow is safe or fully audited.
