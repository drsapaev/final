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
| REG-FE-014 | P2 | Context action acknowledgement | Context menu emits success for status changes even when the action returned null after failure | SOURCE-OBSERVED / REPRO-PENDING | Batch J: action feedback |
| REG-FE-015 | P2 | Partial batch status mutations | A partial server-side success yields an error but no worklist refresh/reconciliation | SOURCE-OBSERVED / REPRO-PENDING | Batch J: action feedback |
| REG-FE-016 | P3 | Cart visit forecast | Wizard banner counts distinct doctor IDs, while the payload groups by resource tag and appointment time too | SOURCE-OBSERVED / REPRO-PENDING | Batch K: cart summary |
| REG-FE-017 | P2 | Cancellation dialog handoff | Null/partial cancellation response can still resolve callback and trigger success/close | SOURCE-OBSERVED / REPRO-PENDING | Batch L: cancellation result contract |
| REG-FE-018 | P2 | Post-wizard reconciliation | Intended retry does not run for swallowed network/429/reference-data failures | SOURCE-OBSERVED / REPRO-PENDING | Batch M: post-save data lifecycle |
| REG-FE-019 | P3 | Wizard success feedback | Wizard and panel both trigger react-toastify success notifications for the same save | SOURCE-OBSERVED / REPRO-PENDING | Batch N: toast ownership |
| REG-FE-020 | P2 | Concurrent request tracking | Superseded request clears shared in-flight guard while newer queue load is still pending | SOURCE-OBSERVED / REPRO-PENDING | Batch O: request lifecycle |
| REG-FE-021 | P2 | Auto-refresh vs modal state | Timer snapshots other dialog flags at effect setup and does not react to their open/close changes | SOURCE-OBSERVED / REPRO-PENDING | Batch O: refresh lifecycle |
| REG-FE-022 | P2 | Synthetic queue number/active indicator | Adapter always creates a queue_numbers entry; a visit without a linked DailyQueue can appear to have an active queue | SOURCE-OBSERVED / REPRO-PENDING | Batch P: queue DTO truth |
| REG-FE-023 | P2 | Schedule-next dead control | Registrar context-menu schedule_next is shown but neither table nor menu action router handles it | SOURCE-OBSERVED / REPRO-PENDING | Batch Q: action exposure/wiring |
| REG-FE-024 | P2 | Aggregated action visibility | Context menu ignores grouped_records.available_actions and hides backend-permitted non-payment actions | SOURCE-OBSERVED / REPRO-PENDING | Batch Q: action exposure/wiring |
| REG-FE-025 | P2 | Force majeure target identity | Row action selects specialist_id from legacy doctor fields, not backend queue-owner scope, for mass queue transfer/cancel | SOURCE-OBSERVED / REPRO-PENDING | Batch R: force-majeure owner boundary |
| REG-FE-026 | P3 | Context-menu reschedule visibility | Menu checks missing can_reschedule/reschedule signal on canonical registrar queue rows while inline reschedule remains accessible | SOURCE-OBSERVED / REPRO-PENDING | Batch Q: action exposure/wiring |
| REG-FE-027 | P2 | Welcome morning doctor summary | Doctor groups use absent legacy IDs and count rows, not distinct patients | SOURCE-OBSERVED / REPRO-PENDING | Batch S: Welcome summary |
| REG-FE-028 | P2 | Welcome filtered-empty presentation | No-match filtered results are presented as an empty queue and offer first-record CTA | SOURCE-OBSERVED / REPRO-PENDING | Batch S: Welcome empty states |
| REG-FE-029 | P2 | Welcome primary load error | With zero rows/dataSource=error there is no error message or retry UI | SOURCE-OBSERVED / REPRO-PENDING | Batch S: Welcome error state |
| REG-FE-030 | P2 | Welcome query scope loss | Quick filter replaces all URL params and drops active date/department/doctor/search scope | SOURCE-OBSERVED / REPRO-PENDING | Batch T: URL filters |
| REG-FE-031 | P3 | Welcome orphaned selection | Selection checkboxes enabled with no bulk-action consumer | SOURCE-OBSERVED / REPRO-PENDING | Batch U: selection UX |
| REG-FE-032 | P3 | Welcome calendar date timezone | History date-only string parsed as UTC and displayed in browser local timezone | SOURCE-OBSERVED / REPRO-PENDING | Batch U: clinic date |
| REG-FE-033 | P3 | Default tabpanel label | All-departments tabpanel has no labelledby; corresponding control is not a real tab | SOURCE-OBSERVED / REPRO-PENDING | Batch U: accessibility |

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


### REG-FE-014 — Context-menu status actions claim success on rejected command (P2 candidate)

**Code evidence:** [useRegistrarRowActions.ts L184–L196](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarRowActions.ts#L184-L196) and [L199–L214](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarRowActions.ts#L199-L214) `await updateAppointmentStatus(...)` and **unconditionally** emit `notify.success` for "in_cabinet" and "complete". [useRegistrarActions.ts L100–L126](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarActions.ts#L100-L126) catches HTTP/contract errors or rejects unsupported actions and resolves **`null`**, rather than rejecting. The latter also emits its own success toast on success, so a successful context action may produce **two** success notifications. [Existing row-actions test L105–L111](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/__tests__/useRegistrarRowActions.test.ts#L105-L111) mocks a void/undefined return and only asserts command invocation.

**Potential impact:** an unsuccessful attempt to send a patient to a room or complete a visit is followed by a contradictory success toast; a genuine success may be toasted twice. Affected surface is the **context menu**, distinct from the earlier Welcome confirmation issue REG-FE-006.

**Fail-first test:** render the row-action hook with `updateAppointmentStatus` returning `null` (for declined backend action, permission failure or network error), confirm the menu action, and assert **zero** success toasts. With an actual successful result, assert one coherent success toast from a single owner, not two. Include both `in_cabinet` and `complete`.

**Remediation direction:** gate the context-menu acknowledgement on an explicit successful command result, ideally centralize success/error notifications in `useRegistrarActions`; preserve confirmation, auth/RBAC and backend-owned available-actions semantics.

### REG-FE-015 — Partial batch status command leaves worklist unsynchronized (P2 candidate)

**Code evidence:** [backend registrar_wizard/_visits.py L1471–L1493](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_wizard/_visits.py#L1471-L1493) executes one command per record and returns `success=false` whenever **any** item failed, with `success_count`, `failed_count` and per-record results. Backend actions are not one all-or-nothing batch transaction; for instance, the cancel-visit record branch explicitly commits within the per-item operation ([L951–L981](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_wizard/_visits.py#L951-L981)); an existing characterization test demonstrates the `success_count=1, failed_count=1` shape ([test_registrar_queue_cancel_r13.py L309–L357](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/tests/characterization/test_registrar_queue_cancel_r13.py#L309-L357)). [useRegistrarActions.ts L67–L81 and L109–L126](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarActions.ts#L67-L126) treats a response with `success=false` as a thrown error, and only refreshes the worklist in the all-success path. Its catch reports an error and returns `null`; neither handler reconciles successful records in a partial outcome.

**Potential impact:** for an aggregated/multi-record action that succeeds on A and fails on B (e.g. concurrent status change or unavailable action), UI can continue displaying A as actionable in the old state, without explaining what succeeded. Repeating the command against stale rows can cause user confusion or an unnecessary second state transition attempt. This is *not* evidence of silent corruption: the server owns validation and may reject the duplicate.

**Fail-first test:** feed `handleStartVisit` and `updateAppointmentStatus` a synthetic response `{success:false,success_count:1,failed_count:1,results:[{success:true,record_id:1},{success:false,record_id:2,error:'conflict'}]}`; assert one authoritative refresh/reconciliation happens even though overall action failed; assert user sees **partial success with failed record details** and cannot misread it as zero committed effects. Test all-failed and all-success outcomes separately, and backend permissions independently.

**Remediation direction:** return typed structured outcomes rather than `null`-only errors for partial batches, refresh after any committed item and present precise partial-result feedback. Do not automatically retry the entire group; first reconcile fresh server state and target only records still actionable. Any implementation crossing visit/queue contracts requires mandatory gate.

### REG-FE-016 — Cart banner counts doctors, not prospective visits (P3 candidate)

**Code evidence:** [CartStepV2.tsx L589–L616](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/CartStepV2.tsx#L589-L616) builds `doctorGroups` keyed by `item.doctor_id || 'no_doctor'`, then labels its size as `Будет создано визитов`. In contrast, the actual payload grouping function [wizardUtils.ts L1084–L1154](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/wizardUtils.ts#L1084-L1154) keys each grouped visit by either **resource queue tag** or **doctor ID**, *plus visit date/time*. Different resource tags with no physician are two groups for save but one `no_doctor` card group in the banner calculation; because this component returns `null` when `groupCount <= 1`, the informative visit-count banner is **absent** in this two-visit scenario. A mixed doctor/resource cart can also undercount when the banner appears. Conversely, the same doctor with different visit times may form two grouped visits while banner still counts one.

**Potential impact:** the registrar sees an inaccurate prospective visit count just before confirming a multi-resource or multi-time booking. This is a presentation forecast issue; it does not assert incorrect backend queue allocation.

**Fail-first test:** for synthetic cart with two doctorless services on different resource tags and same date, assert the banner equals `groupCartItemsByVisit(...).length` (two), and for two same-doctor items with distinct visit times verify both counts. Cover grouped same-doctor same-time case (one). Only claim the payload forecast, not actual persisted visit count until backend reconciliation.

**Remediation direction:** derive prospective count from the same pure grouping used to prepare the request or rename banner to a truthful count of distinct doctors/resource groups. Do not introduce a second client-side queue owner or override backend SSOT.

### Verified guardrails and unconfirmed routing hypothesis

- **Read and write doctor assignment:** [CartStepV2.tsx L310–L331](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/CartStepV2.tsx#L310-L331) uses `filterDoctorsForService`, [wizardUtils.ts L183–L209](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/wizardUtils.ts#L183-L209) honors the pinned `service.doctor_id`, and [backend registrar_doctor_eligibility.py L278–L355](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/services/registrar_doctor_eligibility.py#L278-L355) rejects invalid pinned-doctor/resource routing in write commands. No claim of a missing doctor-owner check is made on the inspected path.
- **Edit delta:** [AppointmentWizardV2.tsx L2394–L2484](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2394-L2484) routes a non-empty edit-delta to `applyRegistrarEditDelta` and returns on success/failure; QR full-update has its own return guard. The old batch→cart fallback at [L2494–L2588](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2494-L2588) is still present but **reachability is unproved** for the current canonical edit pathway; do not promote it to a duplicate-booking P1 without a concrete reproduction.
- **No source edits, no tests:** backend and frontend were inspected read-only. The exact effects of these candidates remain subject to focused regression tests.


### REG-FE-017 — CancelDialog reports success on no-op or partial cancel (P2 candidate)

**Code evidence:** [RegistrarDialogsLayer.tsx L144–L168](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/RegistrarDialogsLayer.tsx#L144-L168) forwards an `onCancel` callback to `CancelDialog`. Its `if (!result) return;` branch resolves the callback normally when `runRegistrarRecordAction` produces `null` after missing record references or action unavailability ([useRegistrarActions.ts L44–L64](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarActions.ts#L44-L64)). For a partial server batch `{success:false,success_count>0,failed_count>0}`, the same callback displays `notify.warning`, refreshes, and resolves. [CancelDialog.tsx L58–L83](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/dialogs/CancelDialog.tsx#L58-L83) treats **every normally resolved** `onCancel` as complete success, displays `toast.success` and calls `onClose()`.

**Potential impact:** a registrar may receive a "record successfully canceled" toast although no record was canceled; partial cancellation may produce a contradictory warning followed by a blanket success toast and automatic close. The user may incorrectly trust the cancellation of outstanding entries. This adds a **dialog-level acknowledgement defect** distinct from REG-FE-015 (stale worklist after partial status changes).

**Fail-first test:** mount `CancelDialog` with real-like `RegistrarDialogsLayer` callback and synthetic records. For `runRegistrarRecordAction→null`, assert *no success toast*, no close, and an explicit error; for `{success:false,success_count:1,failed_count:1}`, assert partial feedback with failed record detail and no blanket complete-success; for all-success, assert exactly one success and close. Cover backend action unavailability and mixed aggregate record refs.

**Fix direction:** define typed outcomes (`all_success`, `partial_success`, `no_op`, `failed`) across the dialog/command boundary. Require explicit positive result before success/close; partial outcomes should be reconciled with backend and identified to the registrar. Avoid interpreting "resolved promise" as proof of committed cancellation.

### REG-FE-018 — Post-wizard retry is bypassed by swallowed fetch failures (P2 candidate)

**Code evidence:** [useRegistrarWizard.ts L154–L168](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWizard.ts#L154-L168) calls `Promise.all([loadAppointmentsRef.current({silent:true}),loadIntegratedData()])` and retries the worklist once only if the promise **rejects**. However [useRegistrarWorklistData.ts L347–L395](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L347-L395) handles HTTP 429 and network/API errors internally, dispatching failure state or returning and **not throwing**. [useRegistrarData.ts L54–L92 and L138–L165](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarData.ts#L54-L165) uses `Promise.allSettled` and catches failed reference-data fetches internally, so the outer `Promise.all` generally resolves even on incomplete data. Non-silent `loadIntegratedData` also clears doctors/services/departments before fetching ([L57–L70](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarData.ts#L57-L70)).

**Potential impact:** after successful creation/edit, the wizard closes and presents a payment/print handoff, but a failed refresh may leave stale worklist rows (or empty reference lists) without executing the documented retry. This is **not** evidence that the successful backend save rolled back; it is a screen-reconciliation contract failure. A later periodic/foreground refresh may eventually repair it.

**Fail-first test:** mock a successfully saved wizard result, make the worklist request respond with 429 or reject, and independently fail one of the reference-data requests. Assert a distinguishable refresh outcome reaches the coordinator, a bounded retry/reconciliation policy actually runs when appropriate, and the user sees a stale-data indication rather than an incorrect claim of refreshed data. Keep committed save success separate from refresh failure. Verify that a 429 cooldown is respected rather than blindly hammering it.

**Fix direction:** return an explicit `LoadOutcome`/failure enum from the fetch hooks (including partial metadata failure) and evaluate it in `handleWizardComplete`; retry only retryable failures and give truthful stale-state feedback. Do not throw from already committed command paths in a way that encourages users to resubmit a booking.

### REG-FE-019 — Duplicate success toasts after wizard save (P3 candidate)

**Code evidence:** [AppointmentWizardV2.tsx L2827–L2835](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2827-L2835) calls `toast.success` immediately before `onComplete?.(result)` in the cart-save path; other successful branches have the same pattern ([L2461–L2468](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2461-L2468)). Parent [useRegistrarWizard.ts L122–L144](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWizard.ts#L122-L144) invokes `notify.success` again on the completion callback. [notify.ts L1–L22](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/services/notify.ts#L1-L22) delegates `notify.success` to the *same* `react-toastify.toast.success`.

**Potential impact:** one successful registration/edit may create two success notifications for the same mutation, increasing noise and reducing clarity when payment/print opens. This is cosmetic/feedback ownership, not a duplicate backend write.

**Fail-first test:** render the wizard and parent callback in a synthetic saved-result path and assert exactly one successful save notification and the intended next dialog; repeat for edit-delta and create-cart.

**Fix direction:** choose one owner for the success toast (typically the orchestration layer) and eliminate duplicate acknowledgement without changing save completion, payment handoff or error semantics.

### Focused review pass: Group 1 — patient registration orchestration (2026-10-30)

**Primary files source-read at `main` SHA `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`:**

- [RegistrarPanel.tsx](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/RegistrarPanel.tsx#L1-L498) — routing, callback composition, open/close entrypoints, worklist and dialog wiring.
- [useRegistrarWizard.ts](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWizard.ts#L1-L196) — reducer transitions, open/edit/create state, post-save refresh and payment/print handoff.
- [RegistrarDialogsLayer.tsx](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/RegistrarDialogsLayer.tsx#L1-L315) — cancellation/payment/wizard dialog callbacks and local ErrorBoundary.

**Cross-checked:** `CancelDialog.tsx`, `useRegistrarActions.ts`, `useRegistrarWorklistData.ts`, `useRegistrarData.ts`, `AppointmentWizardV2.tsx`, `ErrorBoundary.tsx`, `useRegistrarNavigation.ts`, `useRegistrarHotkeys.ts`, `notify.ts`, `useRegistrarDialogs.test.ts` and source contract tests.

**Not re-filed as a new bug:** the wizard reducer deliberately preserves edit state on `SET_OPEN`; direct normal wizard `onClose` in `RegistrarDialogsLayer` resets mode and initialData, and the Ctrl+N/new-appointment explicit path resets them as well. `onEmptyStateCta` opens with `SET_OPEN` only, so a stale-edit concern **needs a realistic preceding close-without-reset reproduction**, not just a theoretical reducer state. Similarly, the local ErrorBoundary does implement an explicit retry handler. No P0/P1 was established in this source-only group.


### REG-FE-020 — Superseded request clears in-flight guard of newer load (P2 candidate)

**Code evidence:** [useRegistrarWorklistData.ts L199–L225](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L199-L225) allows non-auto/manual/date loads to overlap, shares `loadAppointmentsInFlightRef`, and assigns a monotonically increasing `requestId`. [L386–L392](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L386-L392) **always** executes `loadAppointmentsInFlightRef.current = false` in `finally`, even if `isSuperseded()` is true and a newer request is still running. The comment about superseded cleanup applies only to the `LOAD_FINALLY` dispatch, not to this ref. Auto-refresh consults the ref in [L491–L506](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L491-L506). A superseded 429 also updates the shared cooldown without an `isSuperseded()` check ([L348–L356](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L348-L356)).

**Potential impact:** A (slow) → B (newer, still pending) → A settles → shared in-flight flag becomes false while B is pending. On the next auto-refresh tick C can start and claim a newer sequence ID; B's correct response is then discarded as superseded even though C was an unnecessary refresh. If A returns 429, stale A can also suspend auto-refresh for 60 seconds after B has otherwise succeeded. This is **not** evidence that server-side queue priority or numbers change; it is a frontend data freshness/race concern.

**Existing test gap:** [useRegistrarWorklistData.test.ts L290–L368](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/__tests__/useRegistrarWorklistData.test.ts#L290-L368) covers late A settling *after* B, but does not cover A settling **while B remains pending and timer C fires**.

**Fail-first test:** with fake timers/deferred promises start A, B; settle A while B is still in flight; advance 30-second interval and assert *no C request*; resolve B and assert B wins, loading guard releases; also test stale A returning 429 does not start a fresh cooldown that blocks successful B's later refresh. Test silent and non-silent combinations.

**Fix direction:** associate in-flight state and cooldown effects with the currently authoritative request, or use a separate active-request counter and explicit source-aware refresh scheduling. Keep request-sequence/latest-wins behavior; avoid treating all overlapping requests as one Boolean.

### REG-FE-021 — Auto-refresh sees stale snapshots of other dialog states (P2 candidate)

**Code evidence:** [RegistrarPanel.tsx L177–L187](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/RegistrarPanel.tsx#L177-L187) writes the current payment/cancel/print/preview/context/reschedule flags to `anyDialogOpenRef.current` during render. [useRegistrarWorklistData.ts L474–L510](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L474-L510) reads `Boolean(anyDialogOpenRef.current)` **once while creating** its interval. Only `showWizard`, `loadAppointments`, and the stable ref identity are in the effect dependency list; the callback at L491–L506 never rechecks the ref. The code comments explicitly note preserving stale-closure behavior. [useRegistrarWorklistData.test.ts L270–L281](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/__tests__/useRegistrarWorklistData.test.ts#L270-L281) uses a ref with static `current:false`; there is no open/close interval test.

**Potential impact:** if the timer was created with all dialogs closed, opening a payment/cancel/preview dialog alone leaves it running, allowing background queue changes under the modal. Conversely, if the effect initialized when one of these dialogs was open (and returned early), closing it without changing `showWizard` or another dependency may leave periodic refresh **disabled** until an unrelated re-render re-creates the effect. WebSocket-triggered loads are not covered by this pause policy and need separate product decision.

**Fail-first test:** with fake timers, keep `showWizard=false` and stable callback identities. Begin with `anyDialogOpenRef.current=false`, then toggle a payment dialog to true and advance interval: assert the intended pause. Begin with true, close it, advance 30 seconds: assert refresh resumes. Ensure Ctrl+N wizard-open behavior remains intact and tests use synthetic records only.

**Fix direction:** observe other dialog state in the effect dependency model, or check the *latest* `anyDialogOpenRef.current` on each interval tick while maintaining a scheduled timer. Decide the intended real-time behavior explicitly: a previous P-026 note discusses the tradeoff of keeping a background list up to date, whereas R-26 calls for pausing when a modal is open. Preserve actual product contract after the decision, not an accidental ref snapshot.

### REG-FE-022 — Synthetic queue-number presence can create a false active-queue badge (P2 candidate)

**Code evidence:** The backend [registrar_integration/_queue_ops.py L1401–L1460](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_integration/_queue_ops.py#L1401-L1460) initializes `queue_entry_number=idx` and only replaces it when a real queue entry is found; `idx` is a presentation ordinal, not necessarily an allocated queue number. Its owner resolver [L352–L432](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_integration/_queue_ops.py#L352-L432) independently returns `daily_queue_id=None` for a visit or appointment without a proved linked queue. The read model serializes both fields ([registrar_integration/_today_queues.py L588–L600 and L663–L699](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_integration/_today_queues.py#L588-L699)). In the frontend, [registrarQueueAdapter.ts L36–L38 and L104–L122](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarQueueAdapter.ts#L36-L122) unconditionally turns the server `number` (including fallback ordinal) into a one-element `queue_numbers` array. Both [computeDoctorStats / computeDepartmentStats L53–L114](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarWorklistRows.ts#L53-L114) infer `hasActiveQueue` from nonempty `queue_numbers` and a waiting/called/in_service status, without checking a real `daily_queue_id`; [Tabs.tsx L282–L311](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/navigation/Tabs.tsx#L282-L311) presents this as an **active queue** indicator.

**Potential impact:** a confirmed/waiting appointment or visit that has no actual DailyQueue link can show an apparent queue number (even ordinal zero) and trigger the "Активная очередь" status badge. This conflates *scheduled patient* with *allocated queue entry*. Because the ordinal originates in the backend read-model fallback, the robust repair likely requires an explicit canonical `queue_number_assigned`/nullable allocated-number fact, **not** guessing ownership or number assignment in React.

**Fail-first test:** construct a backend-integrated queue read response for a synthetic visit/appointment without a matching queue entry (`daily_queue_id:null`, `status:'waiting'`, `number:0` or the ordinal). Pass it through `adaptQueueEntry` and stats; assert it does not produce an active-queue indicator or a falsely allocated queue number. Also verify the positive path with `daily_queue_id` and valid allocated number and preserve per-entry `queue_owner_kind/id`. Backend integration/contract test should demonstrate the linked and unlinked cases before changing DTOs.

**Fix direction:** canonical backend should distinguish display-order ordinal from allocated queue number and supply the truth to the adapter. This touches queue SSOT/read-model semantics; run the mandatory repository gate before any source change. This candidate is not a claim that wrong numbers were actually allocated.

### Group 2 focused review — queues (2026-10-30)

**Named source files inspected at `main` SHA `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`:** [useRegistrarWorklistData.ts](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L1-L547), [registrarWorklistRows.ts](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarWorklistRows.ts#L1-L477), [registrarQueueAdapter.ts](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarQueueAdapter.ts#L1-L142).

**Necessary cross-checks:** `frontend/src/utils/registrarAggregation.ts`, `frontend/src/utils/dateUtils.ts`, `frontend/src/components/navigation/Tabs.tsx`, `frontend/src/pages/registrar/useRegistrarDoctorWorklistFacts.ts`, `frontend/src/pages/RegistrarPanel.tsx`, three focused test files `__tests__/useRegistrarWorklistData.test.ts`, `__tests__/registrarWorklistRows.test.ts`, `__tests__/registrarQueueAdapter.test.ts`, backend `registrar_integration/_today_queues.py` and `_queue_ops.py`, plus ADR-001. All were read-only; **no tests were executed**.

**Verified positive protections:**

- Worklist flattening maps one backend entry to one row, with no client dedup; per-row `queue_owner_kind/id` and real `daily_queue_id` are passed through instead of deriving owner from a specialty bucket ([adapter L53–L73](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarQueueAdapter.ts#L53-L73)).
- Newer-request ID guard checks after both queue fetch and asynchronous patient enrichment ([worklistData L223–L253; L321–L336](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L223-L336)); existing tests cover late superseded success/failure. This is effective for *row content* even though REG-FE-020 highlights a separate in-flight flag/cooldown issue.
- Client today-date formatter explicitly uses `Asia/Tashkent` ([dateUtils.ts L168–L180](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/utils/dateUtils.ts#L168-L180)), matching backend `timezone`; **no browser-local-timezone defect is claimed**.
- Status and doctor tabs use backend-provided `queue_owner_kind/id` ([registrarWorklistRows.ts L48–L67](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarWorklistRows.ts#L48-L67)). Existing tests cover resource vs doctor identity, scope counters and no-match states.
- REG-FE-002 (all-departments search skips service formatting), REG-FE-005 (URL date reload) and REG-FE-007 (429 state) remain already indexed, **not duplicated**. `computeDepartmentStats.hasActiveQueue` intentionally scans even other-date rows in a pinned unit test ([registrarWorklistRows.test.ts L103–L113](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/__tests__/registrarWorklistRows.test.ts#L103-L113)); treat any policy change there as a separate product/contract decision, not an automatically accepted bug.

**Unnumbered follow-up:** the `queueUpdated` event listener schedules a 300/500 ms `setTimeout` ([useRegistrarWorklistData.ts L421–L453](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L421-L453)) without clearing already scheduled callbacks during cleanup. A post-unmount request is plausible; assign a new finding only after a deterministic unmount/fake-timer test demonstrates material impact. An event is also stamped as recent *before* refresh succeeds, which may delay retry on failed refresh, but overlaps REG-FE-007/020 and needs reproduction.


### REG-FE-023 — Schedule-next action visible but not handled by registrar action router (P2 candidate)

**Code evidence:** [AppointmentContextMenu.tsx L186–L201](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/tables/AppointmentContextMenu.tsx#L186-L201) renders `schedule_next` for every non-doctor view, and [L231–L235](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/tables/AppointmentContextMenu.tsx#L231-L235) invokes `onAction('schedule_next',row)` and closes the menu. The entire [useRegistrarRowActions.ts L170–L258](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarRowActions.ts#L170-L258) switch has no `schedule_next` case (the table switch at [L86–L168](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarRowActions.ts#L86-L168) lacks it as well). Contrast: the separate cardiologist surface handles `schedule_next` explicitly in [CardiologistPanelUnified.tsx L1142–L1145](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/CardiologistPanelUnified.tsx#L1142-L1145). Backend does **not** authorize this action generally for registrars: [_helpers.py L162–L175, L209–L215](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_integration/_helpers.py#L162-L215) offers it only when clinical state, patient identity and permitted physician role match. Context menu does not consult `available_actions`/ `can_schedule_next` for this item.

**Potential impact:** registrar clicks a plausible "Назначить следующий визит" menu item; menu closes with **no workflow** or explanation. If implementers simply wire the doctor action without respecting backend entitlement, it could also violate role boundaries. The defect is in the action's visibility/routing, not proof of a backend authorization bypass.

**Fail-first test:** mount `AppointmentContextMenu` on a synthetic registrar row lacking `schedule_next` authorization and assert the option is absent/disabled with an explained reason; for a role-authorized row where a supported flow exists, assert exactly one typed action routes to the appropriate UI. Assert the registrar action router never silently accepts an advertised unhandled action.

**Fix direction:** remove or entitlement-gate this control from registrar menu until a real, authorized registrar scheduling flow exists. Do not copy a cardiologist-only handler into registrar without explicit domain/RBAC approval and mandatory project gate.

### REG-FE-024 — Aggregated patient rows hide backend-authorized non-payment context actions (P2 candidate)

**Code evidence:** [registrarAggregation.ts L267–L333 and L434–L447](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/utils/registrarAggregation.ts#L267-L447) creates all-departments aggregate rows, storing each record's `available_actions` and `can_*` flags inside `grouped_records` but **not on the aggregate root**. Finalization at [L522–L589](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/utils/registrarAggregation.ts#L522-L589) preserves that shape. [AppointmentContextMenu.tsx L30–L49](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/tables/AppointmentContextMenu.tsx#L30-L49) checks only the root `can_*` flags/`available_actions` for non-payment actions; its `payment` branch deliberately delegates to `getBackendActionAvailability` which supports grouped payment. [useRegistrarActions.ts L45–L63](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarActions.ts#L45-L63) and [registrarHelpers.ts L238–L258](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarHelpers.ts#L238-L258) already support grouped record references and per-record availability for actual backend commands.

**Potential impact:** in the **all-departments** patient-aggregated view, `call/in_cabinet`, `complete`, `cancel`, and `print` can disappear from the context menu despite relevant individual records advertising them. A separate inline cancel control may still exist, so do **not** claim every path for those commands is unusable. Statuses can differ across grouped records; showing an action on **any** group member would require an explicit scope UX, not automatic batch execution on every record.

**Fail-first test:** for synthetic grouped rows containing (a) a single actionable record, (b) two records with the same permitted action, (c) mixed eligible/ineligible records, render context actions and compare with the backend permission model; verify consistent rendering and action selection/partial command semantics, especially `hasBackendAction(...)` all-vs-some policy. Add one actual all-departments view integration test and keep payment unaffected.

**Fix direction:** use the same backend-owned available-actions facts and explicit grouped-record selection/aggregation policy for menu affordances and command routing. No local queue eligibility inference, no auto-forwarding a mass command to a mixed-permission group.

### REG-FE-025 — Force-majeure mass actions target legacy doctor fields instead of canonical queue scope (P2 candidate)

**Code evidence:** [useRegistrarRowActions.ts L246–L252](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarRowActions.ts#L246-L252) opens the force-majeure modal with `specialistId: row.doctor_id || row.specialist_id || null` even when the queue read model includes `queue_owner_kind`, `queue_owner_id` and `daily_queue_id`, passed through in [registrarQueueAdapter.ts L65–L73](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarQueueAdapter.ts#L65-L73). The adapter does **not** populate `doctor_id` from the canonical queue owner. [ForceMajeureModal.tsx L65–L80 and L109–L115 / L143–L149](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/registrar/ForceMajeureModal.tsx#L65-L149) uses this `specialistId` to preview waiting entries and submit **mass transfer or cancellation with refunds**. Backend [force_majeure.py L142–L205](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/force_majeure.py#L142-L205) defines specialist-scoped operations requiring Admin/Registrar; backend registrar row-owner resolver explicitly distinguishes doctor-owned and resource-owned queues ([_queue_ops.py L352–L386](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_integration/_queue_ops.py#L352-L386)).

**Potential impact:** for canonical queue rows with only `queue_owner_id`, the modal can receive null specialist ID, produce no preview, and still offer confirmation actions that the API may reject; for rows containing a legacy doctor ID not matching the actual resource/queue owner, the UI may target a **different doctor's entire queue**. No unsafe mass operation has been reproduced or observed; server validates its own specialist scope and permissions, but the frontend selection is not authoritative.

**Fail-first test:** use a synthetic doctor-owned row (`queue_owner_kind:'doctor',queue_owner_id:7`, missing `doctor_id`), a resource-owned row (`queue_owner_kind:'resource',queue_owner_id:7`, incidental `doctor_id:99`), and aggregated multi-owner row. Assert the modal only opens for a *validated, unambiguous specialist scope* and never derives a target from a patient/legacy field. Backend integration tests must verify what resource-owned and mixed queues permit, and that the dry-run and POST operate on the **same** authorized scope.

**Fix direction:** do not fix this by blindly mapping `queue_owner_id` to `specialist_id`: a resource ID is not a doctor ID. Confirm a backend endpoint contract supporting the relevant owner axis or suppress this action for unsupported scopes. This is a high-impact **queue ownership/payment** domain even though currently categorized provisionally P2: run mandatory repository gate and require explicit safe scope confirmation before implementation.

### REG-FE-026 — Context-menu reschedule option hidden for canonical queue rows (P3 candidate)

**Code evidence:** [AppointmentContextMenu.tsx L162–L168](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/tables/AppointmentContextMenu.tsx#L162-L168) checks `hasBackendAction(row,'reschedule','can_reschedule')`. Canonical [_registrar_available_actions in backend _helpers.py L179–L215](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_integration/_helpers.py#L179-L215) does **not** advertise `reschedule`, and its queue serializer [_queue_ops.py L1213–L1251](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_integration/_queue_ops.py#L1213-L1251) does not serialize `can_reschedule`. The frontend [registrarQueueAdapter.ts L95–L103](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarQueueAdapter.ts#L95-L103) also omits any such flag. Meanwhile inline table control [appointmentsTableColumns.tsx L1285–L1289 and L1464–L1469](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/tables/appointmentsTableColumns.tsx#L1285-L1469) computes `canReschedule` from selected status values and calls the registrar reschedule dialog.

**Potential impact:** the same row may offer "Перенести" as an inline table button but never in the context menu. This is an affordance/consistency issue, not proof of incorrect rescheduling or permission escalation. Correct action eligibility and the backend contract should be resolved before surfacing more options.

**Fail-first test:** render one synthetic eligible row from the canonical `/registrar/queues/today` read model and compare inline/menu availability; assert consistent, backend-authorized rescheduling affordances. Include a status/role where reschedule should *not* be offered; do not assert all `waiting` records are inherently eligible.

**Fix direction:** agree a canonical reschedule eligibility/command contract (or remove the redundant menu item), and make both presentation surfaces consume it rather than relying on ad hoc client-side status tests.

### Group 3 focused review — registrar actions (2026-10-30)

**Primary files read at `main` SHA `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`:** [useRegistrarRowActions.ts](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarRowActions.ts#L1-L269) and [useRegistrarActions.ts](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarActions.ts#L1-L135). **Read-only cross-checks:** `registrarHelpers.ts`, `AppointmentContextMenu.tsx`, `appointmentsTableContracts.ts`, `appointmentsTableColumns.tsx`, `registrarAggregation.ts`, `registrarQueueAdapter.ts`, `ForceMajeureModal.tsx`, `RegistrarDialogsLayer.tsx`, `useRegistrarData.ts`, `CardiologistPanelUnified.tsx`, backend `registrar_wizard/_visits.py`, `registrar_integration/_helpers.py`, `registrar_integration/_queue_ops.py`, `force_majeure.py`, focused `useRegistrarRowActions.test.ts` and `useRegistrarActions.test.ts`, `logger.ts`. No runtime tests executed.

**Existing findings corroborated, not duplicated:** REG-FE-014 (context-menu success after null), REG-FE-015 (partial batch no reconciliation), REG-FE-017 (CancelDialog resolved-`null` false acknowledgement). A meaningful **positive** is that `runRegistrarRecordAction` routes all recognized statuses through one backend `/registrar/records/actions` command API and checks record refs and backend actions before dispatch ([useRegistrarActions.ts L45–L64](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarActions.ts#L45-L64)). `handlePayment` explicitly requires a successful payment summary and deliberately keeps committed payment separate from refresh errors ([L85–L94](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarActions.ts#L85-L94)). Backend has per-item role, lifecycle and rollback protections ([_visits.py L853–L1123](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_wizard/_visits.py#L853-L1123)). None of these prove production acceptance by themselves.

**Privacy note for REG-FE-013, same sanitizer root cause:** [useRegistrarRowActions.ts L66–L74](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarRowActions.ts#L66-L74) logs a `patient` key with the full name; [L86–L99 / L114–L135 / L175–L177](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarRowActions.ts#L86-L177) logs the entire row object in `logger.info` on view/payment/call/complete/context-edit actions. [logger.ts L15–L42 and L101–L140](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/utils/logger.ts#L15-L140) does not list bare `patient` nor `patient_fio` as PHI field aliases; it truncates objects with >15 keys, but narrower synthetic row objects may expose these fields. `logger.info` emits only in development by default. Add synthetic data examples to the same privacy batch; do not claim production disclosure or create a duplicate finding.

**Unlogged/needs product contract:** the table branches invoke status actions without `await` ([useRegistrarRowActions.ts L101–L135](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarRowActions.ts#L101-L135)); existing tests explicitly pin this behavior, and `updateAppointmentStatus` catches failures and emits error toasts. Rapid repeated clicks *may* send overlapping actions, but the backend's transition rules and idempotency contract must be exercised before logging a discrete duplicate-command defect. No P0/P1 was established.


### REG-FE-027 — Welcome morning doctor summary merges unrelated owners and mislabels row counts (P2 candidate)

**Code:** [WelcomeView.tsx L205–L280](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L205-L280) builds its `doctorMap` from `appt.doctor_id || appt.specialist_id`, uses `Врач #${doctorId}` when no name exists, and increments `patientCount` **once per record** while labelling it `Пациентов`. Canonical [registrarQueueAdapter.ts L53–L75](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarQueueAdapter.ts#L53-L75) preserves `queue_owner_kind`, `queue_owner_id`, `daily_queue_id`, `patient_id` but does not synthesize a `doctor_id` from the surrounding specialty bucket. Backend [_queue_ops.py L352–L432](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_integration/_queue_ops.py#L352-L432) distinguishes doctor/resource owners.

**Risk:** canonical doctor/resource entries lacking legacy IDs may be merged into a bogus "Врач #undefined" summary; one patient with two records is counted twice as two "patients". `hasQueue` is computed but not rendered here, so do not claim a false open/closed status is displayed.

**Fail-first test:** render synthetic rows from two doctor-owned queues, a resource-owned queue, an unknown owner, and one patient with two records. Assert owner groups are not collapsed and counts use distinct patients or are accurately labelled as record counts. **Repair:** use canonical owner-aware backend presentation facts (or a typed read-model summary), never infer doctor from queue bucket; clarify scope/date and unknown-owner treatment.

### REG-FE-028 — Welcome filtered-no-match screen falsely says queue is empty (P2 candidate)

**Code:** [WelcomeView.tsx L530–L561](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L530-L561) marks empty when `!appointmentsLoading && dataSource==='api' && filteredAppointments.length===0`; [L591–L615](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L591-L615) shows "Сегодня пока нет записей"/"Создать первую запись". The parent supplies both raw `appointments` and filtered rows ([RegistrarPanel.tsx L350–L395](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/RegistrarPanel.tsx#L350-L395)); main [WorklistView.tsx L213–L269](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WorklistView.tsx#L213-L269) correctly differentiates "nothing matched" vs "no entries". Existing [registrarWorklistRows.test.ts L328–L397](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/__tests__/registrarWorklistRows.test.ts#L328-L397) tests the scope fact, but it is not wired into Welcome.

**Risk:** a failed search or narrow status filter can imply there are no patients and invite an unnecessary new registration. Distinct view surface from already fixed Worklist empty-state behavior.

**Fail-first test:** `appointments.length>0`, `filteredAppointments=[]`, `dataSource='api'`, valid auth; assert "Ничего не найдено" and no first-record text. For a genuinely empty response, assert proper empty queue CTA. **Repair:** share the backend-derived scope classification/view-model facts with Welcome, not duplicated heuristics.

### REG-FE-029 — Primary queue load failure is invisible in Welcome's empty history (P2 candidate)

**Code:** [WelcomeView.tsx L527–L545](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L527-L545) shows `DataSourceIndicator` only when `appointments.length>0`, and its empty-state condition requires `dataSource==='api'`. Table is displayed only when loading or `filteredAppointments.length>0` ([L618–L628](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L618-L628)). Thus with initial `dataSource='error'`, no loading and no rows, there is no dedicated failure/retry state. [WorklistView.tsx L213–L232](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WorklistView.tsx#L213-L232) has one; [useRegistrarWorklistData.ts L114–L136](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L114-L136) preserves this primary-error distinction.

**Risk:** staff may see a blank history region on an otherwise rendered dashboard, without knowing API data failed to load. This does not imply a full-page crash.

**Fail-first test:** render Welcome with zero entries, `dataSource='error'`, `appointmentsLoading=false`, assert visible failure text and retry invoking `loadAppointments`; also cover a previously loaded stale sample. **Repair:** use shared Worklist-style error/stale state and a retry control.

### REG-FE-030 — Welcome quick-filter changes discard unrelated URL scope (P2 candidate)

**Code:** [WelcomeView.tsx L389–L411](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L389-L411) uses `setSearchParams({status:'queued'})` and `setSearchParams({status:'paid_pending'})`, replacing the entire query rather than changing just `status`; the "Все записи" action [L379–L387](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L379-L387) similarly clears all query keys. [useRegistrarNavigation.ts L50–L63, L93–L112](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarNavigation.ts#L50-L112) explicitly syncs department/doctor from query keys and carefully preserves unrelated params in its `clearStatusFilter`.

**Risk:** clicking a status quick filter wipes `date`, `dept`, `doctor_id`, `q`, possibly changing which patients are shown. The status **value** mismatch is already REG-FE-004; this finding concerns the destructive URL update only.

**Fail-first test:** at `/registrar/welcome?date=2026-10-28&dept=lab&q=synthetic`, click each quick filter; verify these keys remain while `status` changes. Decide/document whether "Все записи" means clear status/search or deliberately clear all scope. **Repair:** use functional updates to `URLSearchParams` and mutate only intended keys.

### REG-FE-031 — Welcome selection checkboxes have no bulk-action consumer (P3 candidate)

**Code:** [WelcomeView.tsx L618–L680](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L618-L680) sets `showCheckboxes={true}` with a comment about bulk printing, but does not provide a selection handler or any bulk action. [EnhancedAppointmentsTable.tsx L51–L71, L183–L189](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/tables/EnhancedAppointmentsTable.tsx#L51-L189) keeps local selected rows and renders a "selected N" badge, not a bulk operation. Worklist deliberately sets `showCheckboxes={false}` ([WorklistView.tsx L285–L294](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WorklistView.tsx#L285-L294)) because the bulk action bar was removed.

**Risk:** users can select rows but cannot act on that selection. Not evidence of duplicate backend writes.

**Fail-first test:** render Welcome table, select two rows, verify either a valid bulk-print command exists and uses selection, or selection controls are absent pending product approval. **Repair:** disable orphaned checkboxes unless an authorized bulk operation is truly implemented.

### REG-FE-032 — Welcome history date can shift to the previous day outside clinic timezone (P3 candidate)

**Code:** [WelcomeView.tsx L516–L523](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L516-L523) uses `new Date(historyDate).toLocaleDateString(...)` without an explicit timezone. ISO date-only strings are parsed as UTC midnight, then displayed in the browser's local timezone, showing the previous calendar date in UTC-negative zones. Its hero subtitle [L191–L201](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L191-L201) also uses browser-local today; [dateUtils.ts L168–L180](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/utils/dateUtils.ts#L168-L180) and [WorklistView.tsx L148–L153](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WorklistView.tsx#L148-L153) honor the clinic's Asia/Tashkent time.

**Risk:** remote operator at UTC−5 can see 29 October on a history badge for 30 October while the backend targets 30 October. Display-only, not evidence of wrong queue date.

**Fail-first test:** run synthetic date display under `TZ=America/New_York` with `historyDate='2026-10-30'` and assert 30 October is shown; test clinic-midnight rollover. **Repair:** use shared Tashkent-aware date formatter; keep locale independent of timezone.

### REG-FE-033 — Default all-departments tabpanel has no accessible tab label (P3 candidate)

**Code:** [WorklistView.tsx L122–L133](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WorklistView.tsx#L122-L133) sets `role='tabpanel'` with `aria-labelledby` defined only when a department or doctor is selected. The all-departments control [Tabs.tsx L460–L482](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/navigation/Tabs.tsx#L460-L482) is a plain button outside the tablist, without an `id` or `role='tab'`; doctor/department controls are real tabs ([L490–L524, L573–L589](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/navigation/Tabs.tsx#L490-L589)).

**Risk:** screen readers may encounter a nameless tabpanel in the default view and cannot associate it with the all-departments control. Functional queue data remains unchanged.

**Fail-first test:** run axe/accessibility-tree and keyboard navigation in all-departments, department and doctor modes; check selected tab, tabpanel name, `aria-controls`, focus. **Repair:** make all-departments a coherent tab or expose the default view as a named region instead, while keeping proper accessible navigation.

### Group 4 focused review — interface (2026-10-30)

**Main source baseline:** `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`. **Primary files:** [WorklistView.tsx](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WorklistView.tsx#L1-L334), [WelcomeView.tsx](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L1-L696), [QueueView.tsx](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/QueueView.tsx#L1-L119).

**Cross-checks:** `RegistrarPanel.tsx`, `registrarQueueAdapter.ts`, `registrarWorklistRows.ts`, `useRegistrarWorklistData.ts`, `useRegistrarNavigation.ts`, `dateUtils.ts`, `EnhancedAppointmentsTable.tsx`, `ModernQueueManager.tsx`, `Tabs.tsx`, `registrarCsv.ts`, `registrarWorklistRows.test.ts`, `RegistrarPanel.contract.test.tsx`, and `frontend/e2e/registrar-ux-audit.spec.ts`. **No runtime tests were executed.**

**Previously indexed, not duplicated:** REG-FE-001 row click no-op in Worklist and Welcome; REG-FE-004 quick-filter status names; REG-FE-005 URL date/label; REG-FE-006 missing Welcome status confirmation; REG-FE-008 premature refresh toast; REG-FE-013 development PHI logging (Welcome passes full rows and a name string to `logger.info`, [L629–L661](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L629-L661), with no production disclosure asserted).

**Positive:** Worklist uses an effective counter descriptor, stale/error/retry logic and distinct no-match/empty states, and disables dead selection controls. QueueView forwards URL date/doctor/search values to ModernQueueManager and uses the existing queue update callback ([QueueView.tsx L87–L109](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/QueueView.tsx#L87-L109)); manager responds to date/doctor and queue updates ([ModernQueueManager.tsx L143–L211](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/queue/ModernQueueManager.tsx#L143-L211)). No new separately evidenced defect in QueueView itself in this bounded pass. Existing registrar UX E2E [L178–L218](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/e2e/registrar-ux-audit.spec.ts#L178-L218) checks overflow options and roles, not the missing group-4 regressions.

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
- `frontend/src/pages/registrar/useRegistrarActions.ts` and `useRegistrarRowActions.ts` (context action return contract)
- `backend/app/api/v1/endpoints/registrar_wizard/_visits.py` (per-record action semantics)
- `backend/app/services/registrar_doctor_eligibility.py` (write-side pin and route guards)
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

### Agreed five-group registrar review order

Run **one bounded file group per review pass**; for each group, verify the current `main` SHA, inspect the named files and only their necessary callers/tests/backend contract, de-duplicate against existing IDs, and append source evidence + fail-first tests here. Do not implement app fixes in this audit PR.

1. **Group 1 — patient registration — SOURCE REVIEW DONE (2026-10-30), reproductions pending:** `frontend/src/pages/RegistrarPanel.tsx`, `frontend/src/pages/registrar/useRegistrarWizard.ts`, `frontend/src/pages/registrar/views/RegistrarDialogsLayer.tsx`. Added REG-FE-017–019; earlier cross-cutting issues remain pending tests.
2. **Group 2 — queues — SOURCE REVIEW DONE (2026-10-30), reproductions pending:** `frontend/src/pages/registrar/useRegistrarWorklistData.ts`, `frontend/src/pages/registrar/registrarWorklistRows.ts`, `frontend/src/pages/registrar/registrarQueueAdapter.ts`. Completed bounded read with backend number/owner validation and focused test inspection; added REG-FE-020–022.
3. **Group 3 — registrar actions — SOURCE REVIEW DONE (2026-10-30), reproductions pending:** `frontend/src/pages/registrar/useRegistrarRowActions.ts`, `frontend/src/pages/registrar/useRegistrarActions.ts`. Added REG-FE-023–026; earlier REG-FE-014/015/017 reaffirmed; REG-FE-013 cross-file privacy scope expanded.
4. **Group 4 — interface — SOURCE REVIEW DONE (2026-10-30), reproductions pending:** `frontend/src/pages/registrar/views/WorklistView.tsx`, `frontend/src/pages/registrar/views/WelcomeView.tsx`, `frontend/src/pages/registrar/views/QueueView.tsx`. Group 4 completed; added REG-FE-027–033 (Welcome summary, empty/error feedback, URL filters, dead checkboxes, date formatting and default tabpanel accessibility).
5. **Group 5 — API and integration — systematic review pending:** `frontend/src/api/registrar.ts`, relevant clients/mappers and frontend/backend contract tests. Verify route/version compatibility, typed errors, refresh guarantees and PHI-safe diagnostics.

## Remediation plan — execute only after review triage

1. **Freeze and verify:** complete relevant review slices; fetch latest `main` and compare the old anchored evidence with the new baseline. Confirm each candidate using a fail-first focused unit/component/e2e test; close false positives without editing application code.
2. **Triage risk and ownership:** address confirmed P0/P1 before P2/P3. If any fix touches queue ownership/fairness, clinical lifecycle, payment truth, authentication or API contracts, run the repository-required execution gate and inspect canonical source, ADRs and backend tests before editing.
3. **Batch A — interaction:** `REG-FE-001`; decide desired row-click UX, add keyboard/pointer regression, smallest implementation change, review, CI.
4. **Batch B — view model/localization:** `REG-FE-002` + `REG-FE-003` only if they remain purely presentation-level and independently tested; avoid altering backend SSOT and identity.
5. **Batch C — quick filters and status semantics:** verify REG-FE-004 against canonical queue status and payment-state DTOs.
6. **Batch D — date and refresh lifecycle:** verify REG-FE-005, 007, 008 with effective-date and explicit fetch-state tests.
7. **Batch E — reschedule UI identity:** verify REG-FE-009 with cross-namespace ID collisions.
8. **Batch F — patient selection and persistence:** verify REG-FE-010 and implement an explicit profile-edit contract, if intended.
9. **Batch G — patient/visit partial saves:** verify REG-FE-011; choose safe domain ownership with a mandatory execution gate.
10. **Batch H — asynchronous wizard catalogue:** verify REG-FE-012 with out-of-order responses.
11. **Batch I — PHI-safe diagnostics:** verify/fix REG-FE-013 with synthetic logging tests.
12. **Batch J — registrar command feedback:** verify REG-FE-014/015 with failure and partial-success contract tests; mandatory gate applies if backend action semantics/queue lifecycle is changed.
13. **Batch K — prospective visit count:** verify REG-FE-016 against the same pure grouping that constructs the cart payload.
14. **Batch L — cancellation acknowledgement:** verify REG-FE-017 with a real CancelDialog + handler-level mock and explicit partial/no-op result contract.
15. **Batch M — post-save refresh:** verify REG-FE-018 with rejected/429/degraded integrated-data loads, keeping committed saves independent of refresh.
16. **Batch N — toast ownership:** verify REG-FE-019 and preserve a single save confirmation.
17. **Batch O — queue fetch concurrency and interval modal state:** verify REG-FE-020/021 with deferred network responses and fake timers; distinguish newest-sample integrity from in-flight/429 scheduling and dialog policy.
18. **Batch P — canonical queue allocation fact:** verify REG-FE-022 with backend linked/unlinked queue records and pure adapter→stats tests, run mandatory queue SSOT gate before repair.
19. **Batch Q — action menu contract and wiring:** verify REG-FE-023/024/026 (schedule-next visibility, grouped availability and reschedule affordance). Align UI with backend actions, protect role boundaries; use mandatory gate if backend contract/clinical workflow changes.
20. **Batch R — force-majeure target ownership:** verify REG-FE-025 against doctor/resource/aggregate scopes and backend dry-run+POST consistency; mandatory queue/payment execution gate before any repair.
21. **Batch S — Welcome data/summary truth:** verify REG-FE-027/028/029 with canonical owner, patient and loading/empty/error facts; no frontend business-rule guesses.
22. **Batch T — Welcome URL filter scope:** verify REG-FE-030 and coordinate with REG-FE-004/005, preserving unrelated query keys.
23. **Batch U — selection/date/a11y:** verify REG-FE-031/032/033 with component tests, clinic-zone boundary tests and axe/keyboard.
24. **Additional batches:** one bounded fix PR per validated domain/root cause; never introduce a speculative blanket refactor or mix unrelated source fixes into this ledger PR.
25. **Validation:** relevant Vitest components/contracts, `tsc`/ESLint, affected Playwright flows with synthetic data, relevant queue contract tests, PR quality gates, `git diff --check`, and code review. Record **actual commands/results**; do not claim tests passed without execution.
26. **Closure:** update each ledger row with root cause, test evidence, fix PR/commit SHA, review outcome, and resolution status. Keep this audit PR as the index; merge it only when repository review and CI policy permit. Do not deploy as part of this audit.

## Change log

| Date | Ledger revision | Added / updated | Verification |
| --- | --- | --- | --- |
| 2026-10-29 | Initial | Three provisional source-observed findings; coverage, scope and remediation plan | GitHub source reads; remote PR/commit verified |
| 2026-10-29 | Review pass 2 | REG-FE-004–009: quick filters, URL date, Welcome confirmation, 429 handling, refresh notification, reschedule identity | Frontend hooks/views, backend read-model helpers and existing tests inspected; runtime tests not executed |
| 2026-10-30 | Review pass 3 | REG-FE-010–013: existing patient edits, partial profile/queue save, stale wizard catalogue, development PII logging | Wizard UI/handlers, API mappers, privacy logger, wizard tests inspected; no runtime tests executed; new main source SHA `22b21a8b7c3c0b9b56f4e388c35e329a4321f768` |
| 2026-10-30 | Review pass 4 | REG-FE-014–016: context-action false success, partial batch reconcile, cart visit-count display; pinned doctor/route guard inspected | Backend per-record command path and relevant frontend hooks/tests inspected; no runtime tests executed |
| 2026-10-30 | Five-group protocol / Group 1 | REG-FE-017–019: cancellation acknowledgement, post-wizard retry, duplicate toasts. Ordered remaining Groups 2–5 per user request | Named three files and necessary callers/tests inspected at main SHA `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`; no runtime tests |
| 2026-10-30 | Five-group protocol / Group 2 | REG-FE-020–022: stale request in-flight cleanup, modal interval snapshot, apparent queue number without linked DailyQueue; preexisting REG-FE-002/005/007 not duplicated | Named three files, backend DTO/ownership/number resolver and matching unit tests inspected at main SHA `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`; no runtime tests |
| 2026-10-30 | Five-group protocol / Group 3 | REG-FE-023–026: dead schedule-next action, missing grouped action visibility, force-majeure target mismatch, hidden context reschedule; expanded existing REG-FE-013 evidence without duplicate | Two primary action hooks, context menu, server action/owner contracts, force-majeure and focused tests inspected at main SHA `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`; no runtime tests |
| 2026-10-30 | Five-group protocol / Group 4 | REG-FE-027–033: Welcome summary, filtered/no-data/error semantics, URL query preservation, orphaned selection, clinic date formatting and unlabeled all-departments tabpanel. Existing 001/004/005/006/008/013 not duplicated | Three views, queue manager, adapters, table, navigation and focused tests inspected at main `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`; no runtime tests |

## End-of-review acceptance criteria

- Every finding has a unique stable ID and a final disposition: `CONFIRMED`, `NOT A BUG`, `DUPLICATE`, or `RESOLVED`.
- Confirmed defects have focused regression tests; no test exists merely to silence a failure.
- Changes preserve backend queue fairness, identities, clinical/payment ownership, RBAC, and privacy guardrails.
- Fix PRs are reviewed, all required CI is green, and the final ledger links to those PRs/commits.
- This document by itself is **not evidence** that the registrar workflow is safe or fully audited.
